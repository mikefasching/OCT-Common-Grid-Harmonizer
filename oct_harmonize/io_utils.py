from pathlib import Path
import numpy as np
import imageio.v3 as iio
import SimpleITK as sitk
import json

def load_bscan_image(path: str):
    p = Path(path)
    arr = iio.imread(p)  # supports PNG/JPG/TIFF
    if arr.ndim == 3:
        # convert RGB -> grayscale (luminance approx)
        arr = arr.mean(axis=2)
    dtype = arr.dtype
    return arr.astype(np.float32), dtype

def save_bscan_image(arr: np.ndarray, path: str, dtype_hint=None, bitdepth: int = 8, assume_scaled: bool = False):
    """
    Save B-scan as 8-bit or 16-bit.
    If assume_scaled=True, `arr` is already in [0,1] (no percentile windowing here).
    """
    if assume_scaled:
        scaled = np.clip(arr, 0.0, 1.0).astype(np.float32)
    else:
        hi = np.percentile(arr, 99.9)
        lo = np.percentile(arr, 0.1)
        if hi <= lo:
            scaled = np.zeros_like(arr, dtype=np.float32)
        else:
            scaled = np.clip((arr - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)

    if bitdepth == 16:
        out = (scaled * 65535.0).astype(np.uint16)
    else:
        out = (scaled * 255.0).astype(np.uint8)

    p = Path(path)
    if p.suffix.lower() not in [".png", ".tif", ".tiff"]:
        p = p.with_suffix(".tif" if bitdepth == 16 else ".png")

    iio.imwrite(p, out)


def load_volume(path: str):
    """
    Read 3D medical image (NIfTI/MHD/TIFF stack) and return numpy as [z, x, y].
    SimpleITK returns [z, y, x]; we swap to [z, x, y].
    """
    p = Path(path)
    itk = sitk.ReadImage(str(p))
    arr = sitk.GetArrayFromImage(itk)  # [z, y, x]
    arr = np.transpose(arr, (0, 2, 1))  # -> [z, x, y]
    dtype = arr.dtype
    return arr.astype(np.float32), dtype

def save_volume(vol: np.ndarray, path: str, dtype_hint=None):
    """
    Save as NIfTI by default. Input vol is [z, x, y]; convert back to [z, y, x].
    """
    arr = np.transpose(vol, (0, 2, 1))
    itk = sitk.GetImageFromArray(arr.astype(np.float32))
    sitk.WriteImage(itk, str(Path(path)))

def load_spacing_from_meta(meta: dict):
    """
    Expect keys: 'axial_um', 'lateral_um', 'inter_bscan_um' (last optional for b-scan).
    """
    axial = meta.get("axial_um", None)
    lateral = meta.get("lateral_um", None)
    inter = meta.get("inter_bscan_um", None)
    return axial, lateral, inter

def list_pngs_in_dir(folder: Path):
    exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]
    files.sort()
    return files
