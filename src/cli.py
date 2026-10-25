"""Argomenti da riga di comando condivisi tra gli script."""
import argparse

from .dehaze import DehazeParams


def add_dehaze_args(ap: argparse.ArgumentParser) -> None:
    g = ap.add_argument_group("parametri DCP")
    g.add_argument("--patch", type=int, default=15)
    g.add_argument("--omega", type=float, default=0.95)
    g.add_argument("--t0", type=float, default=0.1)
    g.add_argument("--top-percent", type=float, default=0.001)
    g.add_argument("--airlight", choices=["brightest", "max_per_channel", "mean"], default="brightest")
    g.add_argument("--refine", choices=["guided", "guided_color", "guided_cv", "bilateral", "none"],
                   default="guided")
    g.add_argument("--radius", type=int, default=60)
    g.add_argument("--eps", type=float, default=1e-3)
    g.add_argument("--gamma", type=float, default=None)


def params_from_args(a: argparse.Namespace) -> DehazeParams:
    return DehazeParams(patch=a.patch, omega=a.omega, t0=a.t0, top_percent=a.top_percent,
                        airlight_mode=a.airlight, refine=a.refine, radius=a.radius,
                        eps=a.eps, gamma=a.gamma)