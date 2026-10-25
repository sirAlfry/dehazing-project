"""PSNR e SSIM su immagini float in [0,1]."""
from __future__ import annotations

from typing import cast

import numpy as np
from skimage.metrics import (
    peak_signal_noise_ratio,  # pyright: ignore[reportUnknownVariableType]
    structural_similarity,  # pyright: ignore[reportUnknownVariableType]
)

def mse(pred: np.ndarray, gt: np.ndarray) -> float:
    return float(np.mean((pred.astype(np.float64) - gt.astype(np.float64)) ** 2))


def psnr(pred: np.ndarray, gt: np.ndarray) -> float:
    return float(cast(float, peak_signal_noise_ratio(gt, pred, data_range=1.0)))


def ssim(pred: np.ndarray, gt: np.ndarray) -> float:
    # Con full=False (default) skimage restituisce un solo float: cast lo dice a Pylance.
    # SSIM calcolato per canale e mediato: va DICHIARATO nella relazione.
    return float(cast(float, structural_similarity(gt, pred, data_range=1.0, channel_axis=-1)))