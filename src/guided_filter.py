"""Guided Filter (He, Sun, Tang 2010) — implementazione NumPy/OpenCV a tempo O(N)."""
from __future__ import annotations

import cv2
import numpy as np


def _box(x: np.ndarray, r: int) -> np.ndarray:
    """Media su finestra (2r+1)x(2r+1): costo indipendente da r (immagini integrali)."""
    return cv2.boxFilter(x, ddepth=-1, ksize=(2 * r + 1, 2 * r + 1),
                         normalize=True, borderType=cv2.BORDER_REFLECT)


def guided_filter_gray(I: np.ndarray, p: np.ndarray, r: int, eps: float) -> np.ndarray:
    """Guida in scala di grigi. I, p: HxW float32."""
    mean_I, mean_p = _box(I, r), _box(p, r)
    var_I = _box(I * I, r) - mean_I * mean_I
    cov_Ip = _box(I * p, r) - mean_I * mean_p
    a = cov_Ip / (var_I + eps)            # a_k
    b = mean_p - a * mean_I               # b_k
    return _box(a, r) * I + _box(b, r)    # q_i = ā_i I_i + b̄_i


def guided_filter_color(I: np.ndarray, p: np.ndarray, r: int, eps: float) -> np.ndarray:
    """Guida a colori (HxWx3), versione usata da He per il dehazing: bordi più fedeli.
    Attenzione: usa una matrice 3x3 per pixel -> tanta RAM su immagini enormi."""
    mean_I = _box(I, r)                                    # HxWx3
    mean_p = _box(p, r)                                    # HxW
    cov_Ip = _box(I * p[..., None], r) - mean_I * mean_p[..., None]

    h, w, _ = I.shape
    sigma = np.empty((h, w, 3, 3), np.float32)
    for i in range(3):
        for j in range(i, 3):
            v = _box(I[..., i] * I[..., j], r) - mean_I[..., i] * mean_I[..., j]
            sigma[..., i, j] = v
            sigma[..., j, i] = v
    sigma += eps * np.eye(3, dtype=np.float32)

    a = np.linalg.solve(sigma, cov_Ip[..., None])[..., 0]  # HxWx3
    b = mean_p - (a * mean_I).sum(axis=2)
    return (_box(a, r) * I).sum(axis=2) + _box(b, r)


def guided_filter_opencv(I: np.ndarray, p: np.ndarray, r: int, eps: float) -> np.ndarray:
    """Versione di riferimento di OpenCV (richiede opencv-contrib-python)."""
    return cv2.ximgproc.guidedFilter(guide=I, src=p, radius=r, eps=eps)


def guided_filter(I: np.ndarray, p: np.ndarray, r: int = 60, eps: float = 1e-3) -> np.ndarray:
    """Sceglie automaticamente la versione in base ai canali della guida."""
    guide = I.astype(np.float32)
    src = p.astype(np.float32)
    if guide.ndim == 2:
        return guided_filter_gray(guide, src, r, eps)
    return guided_filter_color(guide, src, r, eps)