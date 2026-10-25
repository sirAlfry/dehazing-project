"""Dehazing di una singola immagine.
Esempio:  python scripts/run_single.py --input data/NH-HAZE/NH-HAZE/01_hazy.png --save-maps
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))          # permette "from src..." lanciando lo script da ovunque

from src.cli import add_dehaze_args, params_from_args   # noqa: E402
from src.dehaze import dehaze_with_maps                           # noqa: E402
from src.io_utils import read_image, resize_max_side, write_image  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Dehazing DCP + Guided Filter su una singola immagine")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default=str(ROOT / "results" / "single"))
    ap.add_argument("--max-side", type=int, default=0, help="ridimensiona se il lato maggiore supera N px")
    ap.add_argument("--save-maps", action="store_true", help="salva anche canale scuro e trasmissioni")
    add_dehaze_args(ap)
    args = ap.parse_args()

    inp, out = Path(args.input), Path(args.output)
    img = resize_max_side(read_image(inp), args.max_side)
    J, maps = dehaze_with_maps(img, params_from_args(args))

    write_image(out / f"{inp.stem}_dehazed.png", J)
    if args.save_maps:
        write_image(out / f"{inp.stem}_dark.png", maps["dark"])
        write_image(out / f"{inp.stem}_t_raw.png", maps["t_raw"])
        write_image(out / f"{inp.stem}_t.png", maps["t"])
    print(f"A (BGR) = {maps['A'].round(3)}  ->  salvato in {out}")


if __name__ == "__main__":
    main()