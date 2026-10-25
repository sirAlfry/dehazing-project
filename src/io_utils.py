"""I/O delle immagini + abbinamento hazy/GT per i dataset del progetto.

Convenzione di TUTTO il progetto: immagini float32, BGR, valori in [0, 1].
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


# ---------------------------------------------------------------- I/O sicuro
def read_image(path: str | Path) -> np.ndarray:
    """Legge un'immagine anche se il percorso contiene caratteri non ASCII
    (es. 'università'): cv2.imread su Windows fallirebbe restituendo None."""
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"Impossibile leggere l'immagine: {path}")
    return img.astype(np.float32) / 255.0


def write_image(path: str | Path, img: np.ndarray) -> None:
    """Salva un'immagine (o una mappa 2D) in [0,1]; crea le cartelle se servono."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    u8 = (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    ok, buf = cv2.imencode(path.suffix or ".png", u8)
    if not ok:
        raise IOError(f"Impossibile codificare l'immagine: {path}")
    buf.tofile(str(path))


def resize_max_side(img: np.ndarray, max_side: int | None) -> np.ndarray:
    """Riduce l'immagine in modo che il lato maggiore sia <= max_side (0/None = no-op)."""
    if not max_side:
        return img
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1.0:
        return img
    return cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)


# ------------------------------------------------------------- dataset
@dataclass(frozen=True)
class Pair:
    name: str
    hazy: Path
    gt: Path


def _images(folder: Path) -> list[Path]:
    """Tutte le immagini nella cartella (ricorsivo, estensione case-insensitive)."""
    return sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS)


def _find_dir(root: Path, name: str) -> Path:
    """Trova una sottocartella con quel nome a qualunque profondità
    (gestisce '# I-HAZY NTIRE 2018/hazy' senza dover rinominare nulla)."""
    for d in sorted(root.rglob("*")):
        if d.is_dir() and d.name.lower() == name.lower():
            return d
    raise FileNotFoundError(f"Cartella '{name}' non trovata sotto {root}")


def pairs_ntire18(root: Path) -> list[Pair]:
    """O-HAZE / I-HAZE: .../hazy/01_outdoor_hazy.jpg  <->  .../GT/01_outdoor_GT.jpg"""
    hazy_dir, gt_dir = _find_dir(root, "hazy"), _find_dir(root, "GT")
    gt = {p.stem.lower().replace("_gt", ""): p for p in _images(gt_dir)}
    pairs: list[Pair] = []
    for h in _images(hazy_dir):
        key = h.stem.lower().replace("_hazy", "")
        if key in gt:
            pairs.append(Pair(key, h, gt[key]))
    return pairs


def pairs_nh(root: Path) -> list[Pair]:
    """NH-HAZE: 01_hazy.png e 01_GT.png nella stessa cartella."""
    imgs = _images(root)
    gt = {p.stem.lower()[:-3]: p for p in imgs if p.stem.lower().endswith("_gt")}
    pairs: list[Pair] = []
    for h in imgs:
        stem = h.stem.lower()
        if stem.endswith("_hazy") and stem[:-5] in gt:
            pairs.append(Pair(stem[:-5], h, gt[stem[:-5]]))
    return pairs


def pairs_sots(root: Path) -> list[Pair]:
    """SOTS: hazy/1400_3.png o hazy/0001_0.8_0.2.jpg  <->  clear/1400.png (ID = prima del '_')."""
    gt = {p.stem: p for p in _images(root / "clear")}
    pairs: list[Pair] = []
    for h in _images(root / "hazy"):
        img_id = h.stem.split("_")[0]
        if img_id in gt:
            pairs.append(Pair(h.stem, h, gt[img_id]))
    return pairs


DATASETS = {
    "o-haze":       ("O-HAZE",              pairs_ntire18),  # atteso: 45
    "i-haze":       ("I-HAZE",              pairs_ntire18),  # atteso: 30
    "nh-haze":      ("NH-HAZE",             pairs_nh),       # atteso: 55
    "sots-indoor":  ("SOTS-RESIDE/indoor",  pairs_sots),     # atteso: 500
    "sots-outdoor": ("SOTS-RESIDE/outdoor", pairs_sots),     # atteso: 500
}


def list_pairs(name: str, data_root: str | Path = "data") -> list[Pair]:
    sub, fn = DATASETS[name]
    pairs = fn(Path(data_root) / sub)
    if not pairs:
        raise RuntimeError(f"Nessuna coppia trovata per '{name}' in {Path(data_root) / sub}")
    return pairs