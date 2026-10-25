"""Dark Channel Prior (He, Sun, Tang 2009): canale scuro, airlight, trasmissione grezza."""
from __future__ import annotations

import cv2
import numpy as np


def min_filter(img2d: np.ndarray, patch: int) -> np.ndarray:
    """Minimo su finestra patch×patch = erosione morfologica (molto più veloce di un for)."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (patch, patch))
    return cv2.erode(img2d, kernel, borderType=cv2.BORDER_REFLECT)


def dark_channel(img: np.ndarray, patch: int = 15) -> np.ndarray:
    """J_dark(x) = min_c ( min_{y∈Ω(x)} J^c(y) ).  img: HxWx3 float32 in [0,1]."""
    return min_filter(img.min(axis=2), patch)


def estimate_atmospheric_light(
    img: np.ndarray, dark: np.ndarray, top_percent: float = 0.001, mode: str = "brightest"
) -> np.ndarray:
    """Stima A dai pixel con canale scuro più alto (top 0,1%).

    mode:
      - "brightest"       : come nel paper di He -> il SINGOLO pixel più luminoso tra i candidati
      - "max_per_channel" : massimo indipendente per canale (formula attuale del README)
      - "mean"            : media dei candidati (più robusta a pixel saturi/lampade)
    """
    n = max(1, int(dark.size * top_percent))
    idx = np.argpartition(dark.ravel(), -n)[-n:]       # indici dei top-n, O(N)
    candidates = img.reshape(-1, 3)[idx]
    if mode == "brightest":
        return candidates[candidates.sum(axis=1).argmax()].astype(np.float32)
    if mode == "max_per_channel":
        return candidates.max(axis=0).astype(np.float32)
    if mode == "mean":
        return candidates.mean(axis=0).astype(np.float32)
    raise ValueError(f"mode sconosciuto: {mode}")

def transmission_raw(img: np.ndarray, A: np.ndarray, omega: float = 0.95, patch: int = 15) -> np.ndarray:
    """t̃(x) = 1 − ω · min_c min_{y∈Ω(x)} I^c(y)/A^c"""
    normalized = img / np.maximum(A, 1e-6)   # broadcasting su HxWx3
    return 1.0 - omega * dark_channel(normalized, patch)