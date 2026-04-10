from __future__ import annotations

import argparse
import json

from _bootstrap import ensure_t1_paths

REPO_ROOT = ensure_t1_paths()

from aiue_t1.image_metrics import compute_image_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two images using the AiUE T1 Python metrics engine.")
    parser.add_argument("--before-path", required=True)
    parser.add_argument("--after-path", required=True)
    parser.add_argument("--sample-width", type=int, default=160)
    parser.add_argument("--sample-height", type=int, default=90)
    parser.add_argument("--histogram-bins", type=int, default=32)
    parser.add_argument("--crop-x", type=float, default=-1.0)
    parser.add_argument("--crop-y", type=float, default=-1.0)
    parser.add_argument("--crop-width", type=float, default=-1.0)
    parser.add_argument("--crop-height", type=float, default=-1.0)
    parser.add_argument("--mask-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    crop_rect = {
        "x": float(args.crop_x),
        "y": float(args.crop_y),
        "width": float(args.crop_width),
        "height": float(args.crop_height),
    }
    payload = compute_image_metrics(
        args.before_path,
        args.after_path,
        sample_width=int(args.sample_width),
        sample_height=int(args.sample_height),
        histogram_bins=int(args.histogram_bins),
        crop_rect=crop_rect,
        mask_path=str(args.mask_path or ""),
    )
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
