"""Pipeline DCP completa: dehaze(img) -> J."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from .dark_channel import dark_channel, estimate_atmospheric_light, transmission_raw
from .guided_filter import guided_filter, guided_filter_opencv


@dataclass
class DehazeParams:
    patch: int = 15
    omega: float = 0.95
    t0: float = 0.1
    top_percent: float = 0.001
    airlight_mode: str = "brightest"   # brightest | max_per_channel | mean
    refine: str = "guided"             # guided | guided_color | guided_cv | bilateral | none
    radius: int = 60
    eps: float = 1e-3
    gamma: Optional[float] = None      # es. 0.8 per schiarire; None = nessun post-processing


def refine_transmission(img: np.ndarray, t_raw: np.ndarray, p: DehazeParams) -> np.ndarray:
    if p.refine == "none":
        return t_raw
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if p.refine == "guided":
        return guided_filter(gray, t_raw, p.radius, p.eps)
    if p.refine == "guided_color":
        return guided_filter(img, t_raw, p.radius, p.eps)
    if p.refine == "guided_cv":
        return guided_filter_opencv(gray, t_raw, p.radius, p.eps)
    if p.refine == "bilateral":
        # bilaterale "semplice" su t; per la versione joint: cv2.ximgproc.jointBilateralFilter
        return cv2.bilateralFilter(t_raw, d=15, sigmaColor=0.1, sigmaSpace=15)
    raise ValueError(f"refine sconosciuto: {p.refine}")


def recover_scene(img: np.ndarray, t: np.ndarray, A: np.ndarray, t0: float) -> np.ndarray:
    """J(x) = (I(x) − A) / max(t(x), t0) + A"""
    t = np.maximum(t, t0)[..., None]
    return np.clip((img - A) / t + A, 0.0, 1.0)


def dehaze_with_maps(
    img: np.ndarray, params: DehazeParams | None = None
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Come dehaze(), ma restituisce anche le mappe intermedie (per figure e debug)."""
    p = params or DehazeParams()
    dark = dark_channel(img, p.patch)                                          # passo 1
    A = estimate_atmospheric_light(img, dark, p.top_percent, p.airlight_mode)  # passo 2
    t_raw = transmission_raw(img, A, p.omega, p.patch)                         # passo 3
    t = np.clip(refine_transmission(img, t_raw, p), 0.0, 1.0)                  # passo 4
    recovered = recover_scene(img, t, A, p.t0)                                 # passo 5
    J = np.power(recovered, p.gamma) if p.gamma else recovered                 # passo 6
    return J, {"dark": dark, "A": A, "t_raw": t_raw, "t": t}


def dehaze(img: np.ndarray, params: DehazeParams | None = None) -> np.ndarray:
    """img: HxWx3 float32 BGR in [0,1]  ->  immagine ripulita J."""
    return dehaze_with_maps(img, params)[0]