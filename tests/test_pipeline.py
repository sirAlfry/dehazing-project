import numpy as np
import pytest

from src.dark_channel import dark_channel
from src.dehaze import DehazeParams, dehaze, recover_scene
from src.guided_filter import guided_filter, guided_filter_color, guided_filter_opencv


def test_guided_filter_su_costante_restituisce_costante():
    I = np.random.rand(64, 64).astype(np.float32)
    p = np.full((64, 64), 0.5, np.float32)
    np.testing.assert_allclose(guided_filter(I, p, r=4, eps=1e-3), 0.5, rtol=0, atol=1e-4)


def test_dark_channel_propaga_il_pixel_nero_nella_finestra():
    img = np.ones((32, 32, 3), np.float32)
    img[10, 10, 1] = 0.0
    d = dark_channel(img, patch=5)
    assert d[10, 10] == 0 and d[12, 12] == 0 and d[0, 0] == 1


def test_recover_scene_inverte_il_modello_fisico():
    rng = np.random.default_rng(0)
    J = rng.random((32, 32, 3), dtype=np.float32)
    A = np.array([0.9, 0.9, 0.9], np.float32)
    t = np.full((32, 32), 0.6, np.float32)
    I = J * t[..., None] + A * (1 - t[..., None])     # sintetizzo la nebbia
    np.testing.assert_allclose(recover_scene(I, t, A, t0=0.1), J, rtol=0, atol=1e-5)


def test_dehaze_shape_e_range():
    img = np.random.rand(48, 64, 3).astype(np.float32)
    J = dehaze(img, DehazeParams(radius=8))
    assert J.shape == img.shape and J.dtype == np.float32
    assert J.min() >= 0 and J.max() <= 1


def test_guided_filter_color_su_costante_restituisce_costante():
    rng = np.random.default_rng(1)
    I = rng.random((64, 64, 3), dtype=np.float32)
    p = np.full((64, 64), 0.5, np.float32)
    np.testing.assert_allclose(guided_filter_color(I, p, r=4, eps=1e-3), 0.5, rtol=0, atol=1e-4)


@pytest.mark.parametrize("canali", [1, 3])
def test_guided_filter_coincide_con_opencv(canali: int):
    """La nostra implementazione (guida grigia o a colori) deve dare lo stesso
    risultato di cv2.ximgproc.guidedFilter, a meno della precisione float32."""
    rng = np.random.default_rng(2)
    shape = (80, 96) if canali == 1 else (80, 96, 3)
    I = rng.random(shape, dtype=np.float32)
    p = rng.random((80, 96), dtype=np.float32)
    nostro = guided_filter(I, p, r=8, eps=1e-2)
    riferimento = guided_filter_opencv(I, p, r=8, eps=1e-2)
    np.testing.assert_allclose(nostro, riferimento, rtol=0, atol=1e-5)
