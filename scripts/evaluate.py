"""Valutazione PSNR/SSIM su un dataset; salva CSV + parametri in results/.
Esempio:  python scripts/evaluate.py --dataset sots-indoor --limit 20
"""
import argparse
import csv
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cli import add_dehaze_args, params_from_args                     # noqa: E402
from src.dehaze import dehaze                                             # noqa: E402
from src.io_utils import DATASETS, list_pairs, read_image, resize_max_side, write_image  # noqa: E402
from src.metrics import psnr, ssim                                        # noqa: E402

Row = dict[str, float | str]   # una riga del CSV: nome (str) + metriche (float)

def main() -> None:
    ap = argparse.ArgumentParser(description="Valutazione DCP su un dataset con ground truth")
    ap.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    ap.add_argument("--data-root", default=str(ROOT / "data"))
    ap.add_argument("--out", default=str(ROOT / "results"))
    ap.add_argument("--max-side", type=int, default=0, help="consigliato 1024 per O-HAZE/I-HAZE")
    ap.add_argument("--limit", type=int, default=0, help="usa solo le prime N coppie (debug)")
    ap.add_argument("--save-images", action="store_true")
    add_dehaze_args(ap)
    args = ap.parse_args()

    params = params_from_args(args)
    pairs = list_pairs(args.dataset, args.data_root)
    if args.limit:
        pairs = pairs[: args.limit]

    run = f"{args.dataset}_p{params.patch}_w{params.omega}_t{params.t0}_{params.refine}_{params.airlight_mode}"
    out_dir = Path(args.out) / run
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "params.json").write_text(
        json.dumps({**asdict(params), "max_side": args.max_side, "n_pairs": len(pairs)}, indent=2))

    rows: list[Row] = []
    for pair in tqdm(pairs, desc=run):
        hazy = resize_max_side(read_image(pair.hazy), args.max_side)
        gt = read_image(pair.gt)
        if gt.shape[:2] != hazy.shape[:2]:
            gt = cv2.resize(gt, (hazy.shape[1], hazy.shape[0]), interpolation=cv2.INTER_AREA)

        start = time.perf_counter()
        J = dehaze(hazy, params)
        elapsed = time.perf_counter() - start

        rows.append({
            "name": pair.name,
            "psnr_hazy": psnr(hazy, gt), "ssim_hazy": ssim(hazy, gt),   # baseline "non faccio nulla"
            "psnr": psnr(J, gt), "ssim": ssim(J, gt),
            "time_s": elapsed,
        })
        if args.save_images:
            write_image(out_dir / "images" / f"{pair.name}.png", J)

    with open(out_dir / "metrics.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{run}  ({len(rows)} immagini)")
    for k in ["psnr_hazy", "ssim_hazy", "psnr", "ssim", "time_s"]:
        v = np.array([r[k] for r in rows])
        print(f"  {k:10s} {v.mean():8.4f} ± {v.std():.4f}")
    print(f"Risultati in {out_dir}")


if __name__ == "__main__":
    main()