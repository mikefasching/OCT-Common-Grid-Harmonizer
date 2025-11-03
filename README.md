# OCT Common Grid Harmonizer

A lightweight Python + Docker pipeline for **resampling Zeiss/Heidelberg OCT B-scans or volumes**
onto a **shared canonical grid** (same physical spacing and image size).

This ensures geometric consistency across scanners, ideal for cross-vendor model training
(e.g., CycleGAN style translation or a vendor-invariant encoder like VILE).

---

## Features

- **2D mode** – process a single B-scan (`--mode bscan`)
- **Folder mode** – process all PNG/JPG/TIFF in a directory (`--mode bscan_dir`)
- **3D mode** – process full OCT volumes (NIfTI/MHD/TIFF stack → NIfTI)
- Fully configurable canonical spacing and output size
- Optional preprocessing (log/gamma undo, percentile normalization, RPE-flatten stub) (needs further development)
- Docker-friendly: adjust everything via CLI flags or environment variables

---

## Installation (Docker)

Build the Docker image:

```bash
docker build -t octcommon .
```

This installs Python 3.11, SimpleITK, imageio, NumPy, and SciPy in a slim container.

---

## Usage

### Folder of PNGs (single vendor → `processed/`)

All images in the input folder share the same vendor spacings.

```bash
docker run --rm -v "$PWD":/data octcommon   --mode bscan_dir   --input_dir /data/raw_pngs   --output_dir /data/processed   --src_axial_um 1.96   --src_lateral_um 11.7   --canon_axial_um 3.0   --canon_lateral_um 12.0   --out_axial_px 640   --out_lateral_px 384   --interp bspline   --normalize
```

> Zeiss → `--src_axial_um 1.96`, `--src_lateral_um 11.7`  
> Heidelberg → `--src_axial_um 3.87`, `--src_lateral_um 6.0`

Each input PNG/JPG/TIFF is resampled, cropped/padded, normalized, and saved to `/data/processed/`
with the same filename.

---

### Single B-scan (PNG/JPG/TIFF → PNG)

```bash
docker run --rm -v "$PWD":/data octcommon   --mode bscan   --input /data/zeiss_bscan.png   --output /data/zeiss_canon.png   --src_axial_um 1.96   --src_lateral_um 11.7   --canon_axial_um 3.0   --canon_lateral_um 12.0   --out_axial_px 640   --out_lateral_px 384   --interp bspline   --normalize
```

---

### Full Volume (NIfTI/MHD/TIFF stack → NIfTI)

```bash
docker run --rm -v "$PWD":/data octcommon   --mode volume   --input /data/heidelberg.nii.gz   --output /data/heidelberg_canon.nii.gz   --src_axial_um 3.87   --src_lateral_um 6.0   --src_inter_bscan_um 30.0   --canon_axial_um 3.0   --canon_lateral_um 12.0   --canon_inter_bscan_um 24.0   --out_axial_px 640   --out_lateral_px 384   --out_slices 64   --interp bspline   --normalize
```

---

## Parameters

| Category | Flag | Description |
|-----------|------|-------------|
| **Input/Output** | `--input`, `--output` | Process a single file (used with `--mode bscan` or `--mode volume`). Specify full container paths like `/data/input.png` and `/data/output.png`. |
|  | `--input_dir`, `--output_dir` | Folder mode (used with `--mode bscan_dir` or `--mode volume_dir`). All images in the input directory are processed and saved to the output directory using the same settings. |
| **Spacing (µm)** | `--src_axial_um`, `--src_lateral_um`, `--src_inter_bscan_um` | Physical spacing of the input image (micrometers per pixel). These values come from the scanner’s metadata. Examples: Zeiss ≈ (1.96, 11.7), Heidelberg ≈ (3.87, 11.5). |
|  | `--canon_axial_um`, `--canon_lateral_um`, `--canon_inter_bscan_um` | Target *canonical* spacing after harmonization (defines your common grid). Example: 3.0 µm axial, 12.0 µm lateral ensures identical physical scale across scanners. |
| **Output size (px)** | `--out_axial_px`, `--out_lateral_px`, `--out_slices` | Final pixel dimensions after resampling. Used to standardize all scans to the same shape. <br> - If set smaller than native → center crop (loss of periphery). <br> - If set larger → padding (edge repeat). <br> - Omit to keep full physical field of view. |
| **Interpolation** | `--interp` | Interpolation used during resampling: <br> 🔹 `linear` – bilinear interpolation; fast, slightly blurrier edges. <br> 🔹 `bspline` – cubic B-spline; smooth gradients, ideal for medical images (recommended). <br> 🔹 `nearest` – nearest-neighbor; use only for segmentation masks or discrete labels. |
| **Preprocessing** | `--undo_log` | Approximate inverse of scanner log/gamma compression. Restores linear reflectivity from display-range OCT images (PNG/JPEG). Recommended for Zeiss/Heidelberg exports which store log-scaled data. |
|  | `--normalize` | Robust percentile normalization (typically 1–99%) mapping intensity range to [0, 1]. Reduces scanner brightness bias and stabilizes model training. Disable if you need absolute reflectivity values for analysis. |
|  | `--rpe_flatten` | Simple placeholder for RPE (retinal pigment epithelium) flattening. In a full implementation, this aligns all scans relative to the RPE surface to remove curvature from foveal dip. Currently performs a minimal geometric normalization only. |
| **General Notes** |  | - `--interp bspline` + `--undo_log` + `--normalize` is a good default combination for B-scans. <br> - To avoid cropping, choose output sizes that match or exceed each vendor’s resampled dimensions. <br> - For 3-D volumes, axial ↔ depth corresponds to voxel z-spacing; lateral ↔ x/y plane. |


---

## Environment Variables

You can override defaults globally (no CLI flag needed):

```bash
-e CANON_AXIAL_UM=2.8
-e CANON_LATERAL_UM=10
-e CANON_INTER_BSCAN_UM=24
-e OUT_AXIAL_PX=704
-e OUT_LATERAL_PX=416
-e OUT_SLICES=72
-e INTERP=linear
```

---

## Output

- `bscan` / `bscan_dir`: **8-bit PNG** (normalized)
- `volume`: **NIfTI (.nii.gz)** (float32)
- Filenames are preserved in folder mode

---

## Conventions

- NumPy arrays → `[z, x, y] = [axial, lateral, slices]`
- SimpleITK uses `(x, y, z)` internally (handled automatically)
- Resampling preserves **physical FOV**, cropping/padding ensures identical size

---

## Example Results

| Vendor | Input Size (px) | Spacing (µm) | Canonical Spacing (µm) | Output Size (px) | Canonical FOV (µm) |
|---------|-----------------|---------------|--------------------------|------------------|---------------------|
| Zeiss | 1024×512 | 1.96×11.7 | 3.0×12.0 | 640×384 | 1920×4608 |
| Heidelberg | 496×768 | 3.87×6.0 | 3.0×12.0 | 640×384 | 1920×4608 |

---

## Notes

- **RPE flattening** is a placeholder — replace with proper segmentation for production.
- Use **16-bit output** for research-grade data.
- Folder mode is **non-recursive** (expects flat directory).

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|--------|-----|
| “No images found” | Wrong path or unsupported format | Ensure PNG/JPG/TIFF directly in folder |
| “Missing spacing” | Source spacing not provided | Add `--src_*` or use `--metadata` JSON |
| Output looks blurry | Too much interpolation | Try `--interp linear` |
| Wrong brightness | Over-normalized | Disable `--undo_log` or `--normalize` |

---

## License

MIT License — free to use for research and academic work.

---

## Acknowledgement

If this tool helps your research, please acknowledge:

> *“OCT Common Grid Harmonizer (Michael Fasching 2025).”*
