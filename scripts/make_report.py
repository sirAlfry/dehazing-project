# pyright: basic
# ^ matplotlib non ha type hint completi: in modalità strict questo file mostrerebbe
#   decine di avvisi "partially unknown" non risolvibili da noi. Il resto del progetto resta strict.
"""Genera i report dei risultati a partire dalle cartelle prodotte da evaluate.py.

Legge ogni  results/<run>/metrics.csv + params.json  e scrive in  report/:
  - risultati.md        report completo: tabelle, statistiche, ablazioni, figure
  - summary.csv         una riga per run (comodo per Excel / tabelle LaTeX)
  - figures/*.png       grafici quantitativi (+ qualitativi con --qualitative)

Esempi:
  python scripts/make_report.py
  python scripts/make_report.py --qualitative     # aggiunge i confronti hazy / DCP / GT
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass, fields
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # nessuna finestra: salva solo su file
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dehaze import DehazeParams  # noqa: E402

DATASET_ORDER = ["sots-indoor", "sots-outdoor", "o-haze", "i-haze", "nh-haze"]
DATASET_INFO: dict[str, tuple[str, str]] = {
    "sots-indoor": ("SOTS indoor", "sintetica, omogenea"),
    "sots-outdoor": ("SOTS outdoor", "sintetica, omogenea"),
    "o-haze": ("O-HAZE", "reale outdoor, omogenea"),
    "i-haze": ("I-HAZE", "reale indoor, omogenea"),
    "nh-haze": ("NH-HAZE", "reale, NON omogenea"),
}
METRICS = ["psnr_hazy", "ssim_hazy", "psnr", "ssim", "time_s"]
DCP_KEYS = [f.name for f in fields(DehazeParams)]
DEFAULTS: dict[str, Any] = asdict(DehazeParams())
COLOR_HAZY = "#9aa0a6"
COLOR_DCP = "#1f6feb"


# ------------------------------------------------------------------ dati
@dataclass
class Run:
    name: str
    dataset: str
    params: dict[str, Any]
    images: list[str]
    m: dict[str, np.ndarray]

    @property
    def n(self) -> int:
        return len(self.images)

    @property
    def d_psnr(self) -> np.ndarray:
        return self.m["psnr"] - self.m["psnr_hazy"]

    @property
    def d_ssim(self) -> np.ndarray:
        return self.m["ssim"] - self.m["ssim_hazy"]

    @property
    def changed(self) -> dict[str, Any]:
        """Parametri DCP diversi dalla configurazione di default."""
        return {k: self.params.get(k) for k in DCP_KEYS if self.params.get(k) != DEFAULTS[k]}

    @property
    def is_baseline(self) -> bool:
        return not self.changed

    def label(self) -> str:
        return "default" if self.is_baseline else ", ".join(f"{k}={v}" for k, v in self.changed.items())


def load_runs(results_dir: Path) -> list[Run]:
    runs: list[Run] = []
    if not results_dir.exists():
        return runs
    for d in sorted(results_dir.iterdir()):
        csv_path, par_path = d / "metrics.csv", d / "params.json"
        if not (d.is_dir() and csv_path.exists() and par_path.exists()):
            continue
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            continue
        params: dict[str, Any] = json.loads(par_path.read_text(encoding="utf-8"))
        runs.append(Run(
            name=d.name,
            dataset=d.name.split("_")[0],
            params=params,
            images=[r["name"] for r in rows],
            m={k: np.array([float(r[k]) for r in rows]) for k in METRICS},
        ))
    order = {name: i for i, name in enumerate(DATASET_ORDER)}
    runs.sort(key=lambda r: (order.get(r.dataset, 99), not r.is_baseline, r.label()))
    return runs


def pretty(dataset: str) -> str:
    return DATASET_INFO.get(dataset, (dataset, ""))[0]


def pm(v: np.ndarray, digits: int) -> str:
    return f"{v.mean():.{digits}f} ± {v.std():.{digits}f}"


def best_of(hazy: np.ndarray, dcp: np.ndarray, digits: int) -> tuple[str, str]:
    """Formatta le due medie mettendo in grassetto la migliore."""
    a, b = pm(hazy, digits), pm(dcp, digits)
    return (a, f"**{b}**") if dcp.mean() >= hazy.mean() else (f"**{a}**", b)


def signed(x: float, digits: int) -> str:
    return f"{x:+.{digits}f}"


# ------------------------------------------------------------------ figure quantitative
def fig_summary(runs: list[Run], out: Path) -> None:
    labels = [pretty(r.dataset) for r in runs]
    x = np.arange(len(runs))
    w = 0.38
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, key, title in [(axes[0], "psnr", "PSNR (dB) ↑"), (axes[1], "ssim", "SSIM ↑")]:
        hazy = [r.m[f"{key}_hazy"] for r in runs]
        dcp = [r.m[key] for r in runs]
        ax.bar(x - w / 2, [v.mean() for v in hazy], w, yerr=[v.std() for v in hazy],
               color=COLOR_HAZY, label="Hazy (nessun dehazing)", capsize=3)
        ax.bar(x + w / 2, [v.mean() for v in dcp], w, yerr=[v.std() for v in dcp],
               color=COLOR_DCP, label="DCP + Guided Filter", capsize=3)
        ax.set_xticks(x, labels)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)
        ax.set_axisbelow(True)
    axes[0].legend(loc="upper right", fontsize=9)
    fig.suptitle("Media ± deviazione standard per dataset")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def fig_delta_box(runs: list[Run], out: Path) -> None:
    labels = [pretty(r.dataset) for r in runs]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    for ax, data, title in [(axes[0], [r.d_psnr for r in runs], "Δ PSNR (dB) = DCP − hazy"),
                            (axes[1], [r.d_ssim for r in runs], "Δ SSIM = DCP − hazy")]:
        ax.boxplot(data, tick_labels=labels, showmeans=True)
        ax.axhline(0, color="#d1242f", lw=1, ls="--")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Miglioramento per immagine (sopra la linea rossa = il DCP migliora)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def fig_scatter(runs: list[Run], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 6))
    lo = min(min(r.m["psnr_hazy"].min(), r.m["psnr"].min()) for r in runs) - 1
    hi = max(max(r.m["psnr_hazy"].max(), r.m["psnr"].max()) for r in runs) + 1
    ax.plot([lo, hi], [lo, hi], color="#d1242f", lw=1, ls="--", label="y = x (nessun effetto)")
    for r in runs:
        ax.scatter(r.m["psnr_hazy"], r.m["psnr"], s=12, alpha=0.6, label=pretty(r.dataset))
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("PSNR immagine hazy (dB)")
    ax.set_ylabel("PSNR dopo DCP (dB)")
    ax.set_title("Ogni punto è un'immagine: sopra la diagonale = migliorata")
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def ablation_series(runs: list[Run]) -> dict[tuple[str, str], list[Run]]:
    """Per ogni (dataset, parametro): i run che differiscono dal default SOLO per quel parametro."""
    series: dict[tuple[str, str], list[Run]] = {}
    for ds in {r.dataset for r in runs}:
        ds_runs = [r for r in runs if r.dataset == ds]
        base = [r for r in ds_runs if r.is_baseline]
        for key in DCP_KEYS:
            var = [r for r in ds_runs if list(r.changed) == [key]]
            if var:
                series[(ds, key)] = base + var
    return series


def fig_ablation(ds: str, key: str, group: list[Run], out: Path) -> bool:
    try:
        xs = [float(r.params[key]) for r in group]
    except (TypeError, ValueError):
        return False  # parametro categorico (es. refine): solo tabella
    order = np.argsort(xs)
    xs_sorted = np.array(xs)[order]
    fig, ax1 = plt.subplots(figsize=(6.5, 4))
    ax1.plot(xs_sorted, [group[i].m["psnr"].mean() for i in order], "o-", color=COLOR_DCP, label="PSNR")
    ax1.set_xlabel(key)
    ax1.set_ylabel("PSNR medio (dB)", color=COLOR_DCP)
    ax2 = ax1.twinx()
    ax2.plot(xs_sorted, [group[i].m["ssim"].mean() for i in order], "s--", color="#bf8700", label="SSIM")
    ax2.set_ylabel("SSIM medio", color="#bf8700")
    ax1.axvline(float(DEFAULTS[key]), color="#9aa0a6", lw=1, ls=":")
    ax1.set_title(f"Ablazione di {key} su {pretty(ds)}")
    ax1.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return True


# ------------------------------------------------------------------ figure qualitative
def fig_qualitative(run: Run, which: str, image_name: str, data_root: Path, out: Path) -> bool:
    """Pannello hazy | DCP | GT | trasmissione per una singola immagine del run."""
    import cv2

    from src.dehaze import dehaze_with_maps
    from src.io_utils import list_pairs, read_image, resize_max_side
    from src.metrics import psnr, ssim

    try:
        pair = next(p for p in list_pairs(run.dataset, data_root) if p.name == image_name)
    except (StopIteration, RuntimeError, FileNotFoundError, KeyError):
        print(f"  [!] immagine '{image_name}' di {run.dataset} non trovata in {data_root}: salto")
        return False

    params = DehazeParams(**{k: run.params[k] for k in DCP_KEYS if k in run.params})
    hazy = resize_max_side(read_image(pair.hazy), int(run.params.get("max_side") or 0))
    gt = read_image(pair.gt)
    if gt.shape[:2] != hazy.shape[:2]:
        gt = cv2.resize(gt, (hazy.shape[1], hazy.shape[0]), interpolation=cv2.INTER_AREA)
    J, maps = dehaze_with_maps(hazy, params)

    def rgb(x: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(x, cv2.COLOR_BGR2RGB)

    panels = [
        (rgb(hazy), f"Hazy — {psnr(hazy, gt):.2f} dB / {ssim(hazy, gt):.3f}", None),
        (rgb(J), f"DCP — {psnr(J, gt):.2f} dB / {ssim(J, gt):.3f}", None),
        (rgb(gt), "Ground truth", None),
        (maps["t"], "Trasmissione t(x) rifinita", "gray"),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.4))
    for ax, (img, title, cmap) in zip(axes, panels):
        ax.imshow(np.clip(img, 0, 1), cmap=cmap, vmin=0, vmax=1)
        ax.set_title(title, fontsize=10)
        ax.axis("off")
    fig.suptitle(f"{pretty(run.dataset)} — {image_name} ({which})", fontsize=12)
    fig.tight_layout()
    fig.savefig(out, dpi=110, bbox_inches="tight", pil_kwargs={"quality": 88})
    plt.close(fig)
    return True


# ------------------------------------------------------------------ testo del report
def reading_notes(r: Run) -> list[str]:
    """Osservazioni automatiche basate sui numeri (da verificare con le figure qualitative)."""
    dp, ds_ = float(r.d_psnr.mean()), float(r.d_ssim.mean())
    imp = float((r.d_psnr > 0).mean()) * 100
    notes = [
        f"In media il DCP {'migliora' if dp > 0 else 'peggiora'} il PSNR di **{abs(dp):.2f} dB** "
        f"e {'migliora' if ds_ > 0 else 'peggiora'} la SSIM di **{abs(ds_):.3f}**; "
        f"il PSNR migliora su **{imp:.0f}%** delle immagini.",
    ]
    if dp < 0:
        notes.append("Il PSNR medio scende sotto quello dell'immagine non elaborata: il prior qui non regge. "
                     "Causa tipica: ampie superfici chiare o bianche (pareti, cielo) hanno un canale scuro alto "
                     "anche senza nebbia, quindi la trasmissione viene sottostimata e la scena esce troppo scura "
                     "(limite dichiarato da He et al.). Da provare: `--omega` più basso, `--t0` più alto, "
                     "`--gamma` < 1.")
    if r.dataset == "i-haze":
        notes.append("Scene indoor: luce artificiale e finestre sono spesso i punti più luminosi e la nebbia "
                     "è leggera, quindi il margine di miglioramento è piccolo e l'errore del prior pesa di più.")
    if r.dataset == "nh-haze":
        notes.append("Nebbia non omogenea: il modello assume una sola airlight A e una nebbia che dipende "
                     "solo dalla profondità, quindi un miglioramento limitato è il comportamento atteso.")
    if r.dataset.startswith("sots") and dp > 0:
        notes.append("Dati sintetici generati proprio con il modello di scattering atmosferico: è il caso "
                     "favorevole per il DCP, utile come limite superiore delle prestazioni.")
    return notes


def build_markdown(runs: list[Run], fig_dir: Path, qual: dict[str, list[tuple[str, str, Path]]]) -> str:
    base = [r for r in runs if r.is_baseline]

    def rel(p: Path) -> str:
        return p.relative_to(fig_dir.parent).as_posix()

    L: list[str] = []
    add = L.append

    add("# Report dei risultati — DCP + Guided Filter")
    add("")
    add(f"_Generato automaticamente da `scripts/make_report.py` il {date.today():%d/%m/%Y} "
        f"a partire da {len(runs)} esecuzioni in `results/`. Non modificare a mano: rilancia lo script._")
    add("")

    # --- configurazione
    add("## Configurazione di riferimento")
    add("")
    add("| Parametro | Valore | Significato |")
    add("|---|---|---|")
    meaning = {
        "patch": "lato della finestra Ω del canale scuro (px)",
        "omega": "frazione di nebbia rimossa (ω)",
        "t0": "soglia minima della trasmissione",
        "top_percent": "frazione di pixel candidati per l'airlight",
        "airlight_mode": "come si sceglie A tra i candidati",
        "refine": "metodo di rifinitura della trasmissione",
        "radius": "raggio r del guided filter (px)",
        "eps": "regolarizzazione ε del guided filter",
        "gamma": "correzione gamma finale (vuoto = nessuna)",
    }
    for k in DCP_KEYS:
        add(f"| `{k}` | {DEFAULTS[k] if DEFAULTS[k] is not None else '—'} | {meaning.get(k, '')} |")
    sides = sorted({int(r.params.get("max_side") or 0) for r in base})
    side_txt = ", ".join("originale" if s == 0 else f"{s} px" for s in sides)
    add("")
    add(f"Lato massimo delle immagini durante la valutazione: **{side_txt}**. "
        "Metriche calcolate su valori in [0, 1]; SSIM calcolata per canale e mediata. "
        "I tempi sono misurati sulla CPU della macchina che ha eseguito `evaluate.py`.")
    add("")

    # --- riepilogo
    add("## Riepilogo")
    add("")
    if not base:
        add("Nessun run con i parametri di default: lancia prima `scripts/evaluate.py` senza opzioni DCP.")
        add("")
    else:
        add("| Dataset | Nebbia | N | PSNR hazy | PSNR DCP | Δ PSNR | SSIM hazy | SSIM DCP | Δ SSIM "
            "| Migliorate (PSNR) | Tempo medio |")
        add("|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
        for r in base:
            ph, pd = best_of(r.m["psnr_hazy"], r.m["psnr"], 2)
            sh, sd = best_of(r.m["ssim_hazy"], r.m["ssim"], 3)
            add(f"| {pretty(r.dataset)} | {DATASET_INFO.get(r.dataset, ('', ''))[1]} | {r.n} "
                f"| {ph} | {pd} | {signed(float(r.d_psnr.mean()), 2)} "
                f"| {sh} | {sd} | {signed(float(r.d_ssim.mean()), 3)} "
                f"| {(r.d_psnr > 0).mean() * 100:.0f}% | {r.m['time_s'].mean() * 1000:.0f} ms |")
        add("")
        add("Valori: media ± deviazione standard sulle immagini del dataset. "
            "\"Hazy\" è la baseline senza alcun dehazing (immagine annebbiata confrontata con la GT); "
            "in grassetto il valore migliore tra i due.")
        add("")
        add(f"![Media PSNR e SSIM per dataset]({rel(fig_dir / 'summary_psnr_ssim.png')})")
        add("")
        add(f"![Distribuzione del miglioramento per immagine]({rel(fig_dir / 'delta_boxplot.png')})")
        add("")
        add(f"![PSNR prima e dopo, per immagine]({rel(fig_dir / 'scatter_psnr.png')})")
        add("")

    # --- dettaglio per dataset
    add("## Dettaglio per dataset")
    add("")
    for r in base:
        name, kind = DATASET_INFO.get(r.dataset, (r.dataset, ""))
        add(f"### {name}")
        add("")
        add(f"{r.n} coppie, nebbia {kind}. Cartella dei risultati: `results/{r.name}/`.")
        add("")
        add("| Metrica | Media | Dev. std | Mediana | Min | Max |")
        add("|---|--:|--:|--:|--:|--:|")
        for key, lab, dg in [("psnr_hazy", "PSNR hazy (dB)", 2), ("psnr", "PSNR DCP (dB)", 2),
                             ("ssim_hazy", "SSIM hazy", 3), ("ssim", "SSIM DCP", 3)]:
            v = r.m[key]
            add(f"| {lab} | {v.mean():.{dg}f} | {v.std():.{dg}f} | {np.median(v):.{dg}f} "
                f"| {v.min():.{dg}f} | {v.max():.{dg}f} |")
        add("")
        for note in reading_notes(r):
            add(f"- {note}")
        add("")
        order = np.argsort(r.d_psnr)
        add("| | Immagine | PSNR hazy | PSNR DCP | Δ PSNR | SSIM DCP |")
        add("|---|---|--:|--:|--:|--:|")
        picks = [("migliore", i) for i in order[::-1][:3]] + [("peggiore", i) for i in order[:3]]
        for tag, i in picks:
            add(f"| {tag} | `{r.images[i]}` | {r.m['psnr_hazy'][i]:.2f} | {r.m['psnr'][i]:.2f} "
                f"| {signed(float(r.d_psnr[i]), 2)} | {r.m['ssim'][i]:.3f} |")
        add("")
        for which, img_name, path in qual.get(r.name, []):
            add(f"![{name} — {img_name} ({which})]({rel(path)})")
            add("")

    # --- ablazioni
    add("## Ablazioni")
    add("")
    others = [r for r in runs if not r.is_baseline]
    if not others:
        add("Non ci sono ancora run con parametri diversi dal default. Esempio (PowerShell) per "
            "l'ablazione di ω su SOTS indoor:")
        add("")
        add("```powershell")
        add("foreach ($w in 0.8, 0.85, 0.9, 1.0) { python scripts/evaluate.py --dataset sots-indoor --omega $w }")
        add("python scripts/make_report.py")
        add("```")
        add("")
        add("Ogni run finisce in una cartella diversa e questo report lo include da solo, con tabella e grafico.")
        add("")
    else:
        for ds in DATASET_ORDER + sorted({r.dataset for r in runs} - set(DATASET_ORDER)):
            ds_runs = [r for r in runs if r.dataset == ds]
            if len(ds_runs) < 2:
                continue
            add(f"### {pretty(ds)}")
            add("")
            add("| Variante | N | PSNR DCP | SSIM DCP | Δ PSNR vs hazy | Tempo medio |")
            add("|---|--:|--:|--:|--:|--:|")
            for r in ds_runs:
                add(f"| {r.label()} | {r.n} | {pm(r.m['psnr'], 2)} | {pm(r.m['ssim'], 3)} "
                    f"| {signed(float(r.d_psnr.mean()), 2)} | {r.m['time_s'].mean() * 1000:.0f} ms |")
            add("")
            for sds, key in sorted(ablation_series(runs)):
                path = fig_dir / f"ablation_{sds}_{key}.png"
                if sds == ds and path.exists():
                    add(f"![Ablazione di {key} su {pretty(ds)}]({rel(path)})")
                    add("")
    return "\n".join(L).rstrip() + "\n"


def write_summary_csv(runs: list[Run], out: Path) -> None:
    cols = ["run", "dataset", "variante", "n"] + [f"{k}_{s}" for k in METRICS for s in ("mean", "std")] + \
           ["delta_psnr_mean", "delta_ssim_mean", "improved_psnr_pct", "max_side"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in runs:
            row: list[Any] = [r.name, r.dataset, r.label(), r.n]
            for k in METRICS:
                row += [f"{r.m[k].mean():.6f}", f"{r.m[k].std():.6f}"]
            row += [f"{r.d_psnr.mean():.6f}", f"{r.d_ssim.mean():.6f}",
                    f"{(r.d_psnr > 0).mean() * 100:.1f}", r.params.get("max_side", 0)]
            w.writerow(row)


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser(description="Genera report/ a partire da results/")
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--out", default=str(ROOT / "report"))
    ap.add_argument("--data-root", default=str(ROOT / "data"), help="serve solo con --qualitative")
    ap.add_argument("--qualitative", action="store_true",
                    help="rielabora migliore/mediana/peggiore immagine di ogni dataset e salva i confronti")
    args = ap.parse_args()

    runs = load_runs(Path(args.results))
    if not runs:
        sys.exit(f"Nessun risultato trovato in {args.results}: lancia prima scripts/evaluate.py")

    out = Path(args.out)
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    base = [r for r in runs if r.is_baseline]
    if base:
        fig_summary(base, fig_dir / "summary_psnr_ssim.png")
        fig_delta_box(base, fig_dir / "delta_boxplot.png")
        fig_scatter(base, fig_dir / "scatter_psnr.png")
    for (ds, key), group in ablation_series(runs).items():
        fig_ablation(ds, key, group, fig_dir / f"ablation_{ds}_{key}.png")

    qual: dict[str, list[tuple[str, str, Path]]] = {}
    if args.qualitative:
        for r in base:
            order = np.argsort(r.d_psnr)
            for which, i in [("migliore", order[-1]), ("mediana", order[len(order) // 2]), ("peggiore", order[0])]:
                path = fig_dir / f"qual_{r.dataset}_{which}.jpg"
                print(f"  figura qualitativa: {r.dataset} / {r.images[i]} ({which})")
                if fig_qualitative(r, which, r.images[i], Path(args.data_root), path):
                    qual.setdefault(r.name, []).append((which, r.images[i], path))

    (out / "risultati.md").write_text(build_markdown(runs, fig_dir, qual), encoding="utf-8")
    write_summary_csv(runs, out / "summary.csv")
    print(f"Report scritto in {out / 'risultati.md'} ({len(runs)} run)")


if __name__ == "__main__":
    main()
