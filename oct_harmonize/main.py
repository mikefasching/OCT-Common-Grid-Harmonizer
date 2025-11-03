import os
import json
import argparse
from pathlib import Path

from .io_utils import (
    load_bscan_image,
    save_bscan_image,
    load_volume,
    save_volume,
    load_spacing_from_meta,
    list_pngs_in_dir
)
from .preproc import (
    maybe_undo_log_gamma,
    percentile_normalize,
    rpe_flatten_stub
)
from .geom import (
    resample_2d_to_spacing,
    resample_3d_to_spacing,
    center_crop_pad_2d,
    center_crop_pad_3d
)

def parse_args():
    p = argparse.ArgumentParser(
        description="Resample Zeiss/Heidelberg OCT B-scans or volumes to a common canonical grid."
    )
    p.add_argument("--mode", choices=["bscan", "bscan_dir", "volume"], required=True)

    # I/O
    p.add_argument("--input", help="Input file (bscan: PNG/JPG/TIFF; volume: NIfTI/MHD/TIFF-stack).")
    p.add_argument("--output", help="Output file (bscan: PNG; volume: NIfTI).")

    # Folder mode
    p.add_argument("--input_dir", type=str, help="Folder with input PNG/JPG/TIFF B-scans (single vendor).")
    p.add_argument("--output_dir", type=str, help="Folder to write processed B-scans (created if needed).")

    # Canonical spacing (microns). For volume: z=axial, x=lateral, y=inter-B-scan spacing.
    p.add_argument("--canon_axial_um", type=float, default=float(os.getenv("CANON_AXIAL_UM", 3.0)))
    p.add_argument("--canon_lateral_um", type=float, default=float(os.getenv("CANON_LATERAL_UM", 12.0)))
    p.add_argument("--canon_inter_bscan_um", type=float, default=float(os.getenv("CANON_INTER_BSCAN_UM", 24.0)))

    # Output shapes (pixels). For volume, order is z,x,y.
    p.add_argument("--out_axial_px", type=int, default=int(os.getenv("OUT_AXIAL_PX", 640)))
    p.add_argument("--out_lateral_px", type=int, default=int(os.getenv("OUT_LATERAL_PX", 384)))
    p.add_argument("--out_slices", type=int, default=int(os.getenv("OUT_SLICES", 64)))  # only used for volume

    # Source spacing (override or read from metadata)
    p.add_argument("--src_axial_um", type=float, default=None)
    p.add_argument("--src_lateral_um", type=float, default=None)
    p.add_argument("--src_inter_bscan_um", type=float, default=None)
    p.add_argument("--metadata", type=str, default=None,
                   help="Optional JSON with vendor spacing. Keys: axial_um, lateral_um, inter_bscan_um")

    # Preprocessing toggles
    p.add_argument("--undo_log", action="store_true", help="Heuristic undo of log/gamma compression.")
    p.add_argument("--normalize", action="store_true", help="Percentile normalization to [0,1].")
    p.add_argument("--rpe_flatten", action="store_true", help="(Stub) simple RPE flattening.")
    p.add_argument("--bitdepth", type=int, default=8, help="Bit depth for output images (8 or 16). Default: 8.")

    # Interpolation
    p.add_argument("--interp", choices=["linear", "bspline", "nearest"], default=os.getenv("INTERP", "bspline"))

    return p.parse_args()

def main():
    args = parse_args()

    # Resolve optional global metadata file for spacing
    meta_ax = meta_lat = meta_ib = None
    if args.metadata:
        with open(args.metadata, "r") as f:
            meta = json.load(f)
        meta_ax, meta_lat, meta_ib = load_spacing_from_meta(meta)

    # Common CLI → internal spacing resolution
    s_ax = args.src_axial_um or meta_ax
    s_lat = args.src_lateral_um or meta_lat
    s_ib  = args.src_inter_bscan_um or meta_ib

    # --- Single B-Scan ---
    if args.mode == "bscan":
        if not args.input or not args.output:
            raise ValueError("bscan mode requires --input and --output.")
        if s_ax is None or s_lat is None:
            raise ValueError("bscan mode requires src spacings: --src_axial_um and --src_lateral_um, or --metadata.")

        img, dtype = load_bscan_image(args.input)

        if args.undo_log:
            img = maybe_undo_log_gamma(img)

        rs = resample_2d_to_spacing(
            img=img,
            src_axial_um=s_ax,
            src_lateral_um=s_lat,
            canon_axial_um=args.canon_axial_um,
            canon_lateral_um=args.canon_lateral_um,
            interp=args.interp
        )

        if args.rpe_flatten:
            rs = rpe_flatten_stub(rs)

        out = center_crop_pad_2d(
            rs,
            out_axial_px=args.out_axial_px,
            out_lateral_px=args.out_lateral_px
        )

        if args.normalize:
            out = percentile_normalize(out)

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        save_bscan_image(out, args.output, dtype_hint=dtype, bitdepth=args.bitdepth, assume_scaled=args.normalize)
        print(f"[OK] Saved canonical B-scan to {args.output}")
        return

    # --- Folder of B-Scans (single vendor) ---
    if args.mode == "bscan_dir":
        if not args.input_dir or not args.output_dir:
            raise ValueError("bscan_dir mode requires --input_dir and --output_dir.")
        if s_ax is None or s_lat is None:
            raise ValueError("bscan_dir mode requires src spacings: --src_axial_um and --src_lateral_um, or --metadata.")

        in_dir = Path(args.input_dir)
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        files = list_pngs_in_dir(in_dir)  # assumes PNG/JPG/TIFF; keep your helper
        if not files:
            raise ValueError(f"No PNG/JPG/TIFF images found in {in_dir}")

        for f in files:
            img, dtype = load_bscan_image(str(f))

            im = img
            if args.undo_log:
                im = maybe_undo_log_gamma(im)

            rs = resample_2d_to_spacing(
                img=im,
                src_axial_um=s_ax,
                src_lateral_um=s_lat,
                canon_axial_um=args.canon_axial_um,
                canon_lateral_um=args.canon_lateral_um,
                interp=args.interp
            )

            if args.rpe_flatten:
                rs = rpe_flatten_stub(rs)

            out = center_crop_pad_2d(
                rs,
                out_axial_px=args.out_axial_px,
                out_lateral_px=args.out_lateral_px
            )

            if args.normalize:
                out = percentile_normalize(out)

            # choose extension by bit depth (16-bit -> .tif, else keep original)
            suffix = ".tif" if args.bitdepth == 16 else f.suffix
            out_path = (out_dir / f.name).with_suffix(suffix)

            # use out_path (NOT args.output) in folder mode
            save_bscan_image(out, str(out_path), dtype_hint=dtype, bitdepth=args.bitdepth, assume_scaled=args.normalize)
            print(f"[OK] {f.name} -> {out_path}")

        print(f"[DONE] Processed {len(files)} images into {out_dir}")
        return

    # --- 3D Volume ---
    if args.mode == "volume":
        if not args.input or not args.output:
            raise ValueError("volume mode requires --input and --output.")
        if s_ax is None or s_lat is None or s_ib is None:
            raise ValueError("volume mode requires src spacings: --src_axial_um, --src_lateral_um, --src_inter_bscan_um (or --metadata).")

        vol, dtype = load_volume(args.input)  # numpy [z, x, y]

        if args.undo_log:
            vol = maybe_undo_log_gamma(vol)

        vol_rs = resample_3d_to_spacing(
            vol=vol,
            src_axial_um=s_ax,
            src_lateral_um=s_lat,
            src_inter_bscan_um=s_ib,
            canon_axial_um=args.canon_axial_um,
            canon_lateral_um=args.canon_lateral_um,
            canon_inter_bscan_um=args.canon_inter_bscan_um,
            interp=args.interp
        )

        if args.rpe_flatten:
            vol_rs = rpe_flatten_stub(vol_rs)  # placeholder

        out = center_crop_pad_3d(
            vol_rs,
            out_axial_px=args.out_axial_px,
            out_lateral_px=args.out_lateral_px,
            out_slices=args.out_slices
        )

        if args.normalize:
            out = percentile_normalize(out)

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        save_volume(out, args.output, dtype_hint=dtype)
        print(f"[OK] Saved canonical volume to {args.output}")
        return

if __name__ == "__main__":
    main()
