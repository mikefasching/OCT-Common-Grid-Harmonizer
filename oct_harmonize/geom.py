import numpy as np
import SimpleITK as sitk

def _sitk_interp(name: str):
    if name == "linear":
        return sitk.sitkLinear
    if name == "bspline":
        return sitk.sitkBSpline
    if name == "nearest":
        return sitk.sitkNearestNeighbor
    return sitk.sitkBSpline

def resample_2d_to_spacing(img: np.ndarray,
                           src_axial_um: float,
                           src_lateral_um: float,
                           canon_axial_um: float,
                           canon_lateral_um: float,
                           interp: str = "bspline") -> np.ndarray:
    """
    img shape: [axial (rows), lateral (cols)]
    """
    assert img.ndim == 2
    h, w = img.shape
    phys_y = h * src_axial_um
    phys_x = w * src_lateral_um

    new_h = int(round(phys_y / canon_axial_um))
    new_w = int(round(phys_x / canon_lateral_um))

    itk = sitk.GetImageFromArray(img.astype(np.float32))
    itk.SetSpacing((src_lateral_um, src_axial_um))  # (x=lateral, y=axial)
    resampler = sitk.ResampleImageFilter()
    resampler.SetInterpolator(_sitk_interp(interp))
    resampler.SetOutputSpacing((canon_lateral_um, canon_axial_um))
    resampler.SetSize([new_w, new_h])
    resampler.SetOutputOrigin((0.0, 0.0))
    resampler.SetOutputDirection((1.0, 0.0, 0.0, 1.0))
    out = resampler.Execute(itk)
    return sitk.GetArrayFromImage(out)

def resample_3d_to_spacing(vol: np.ndarray,
                           src_axial_um: float,
                           src_lateral_um: float,
                           src_inter_bscan_um: float,
                           canon_axial_um: float,
                           canon_lateral_um: float,
                           canon_inter_bscan_um: float,
                           interp: str = "bspline") -> np.ndarray:
    """
    vol shape: [z, x, y] = [axial, lateral, slices]
    SimpleITK uses spacing order (x, y, z) -> (cols, rows, slices).
    We'll transpose accordingly.
    """
    assert vol.ndim == 3
    z, x, y = vol.shape

    # Physical size of source
    phys_z = z * src_axial_um
    phys_x = x * src_lateral_um
    phys_y = y * src_inter_bscan_um

    # Target voxel counts at canonical spacing
    new_z = int(round(phys_z / canon_axial_um))
    new_x = int(round(phys_x / canon_lateral_um))
    new_y = int(round(phys_y / canon_inter_bscan_um))

    # Convert to sitk image with spacing (x,y,z)
    vol_for_sitk = np.transpose(vol, (1, 2, 0))  # [x, y, z]
    itk = sitk.GetImageFromArray(vol_for_sitk.astype(np.float32), isVector=False)
    itk.SetSpacing((src_lateral_um, src_inter_bscan_um, src_axial_um))  # (x, y, z)

    resampler = sitk.ResampleImageFilter()
    resampler.SetInterpolator(_sitk_interp(interp))
    resampler.SetOutputSpacing((canon_lateral_um, canon_inter_bscan_um, canon_axial_um))
    resampler.SetSize([new_x, new_y, new_z])
    resampler.SetOutputOrigin((0.0, 0.0, 0.0))
    resampler.SetOutputDirection(np.eye(3).flatten().tolist())

    out = resampler.Execute(itk)
    out_np = sitk.GetArrayFromImage(out)  # [x, y, z]
    out_np = np.transpose(out_np, (2, 0, 1))  # back to [z, x, y]
    return out_np

def center_crop_pad_2d(a: np.ndarray, out_axial_px: int, out_lateral_px: int) -> np.ndarray:
    h, w = a.shape
    pad_h = max(0, out_axial_px - h)
    pad_w = max(0, out_lateral_px - w)
    if pad_h or pad_w:
        a = np.pad(a, ((pad_h//2, pad_h - pad_h//2),
                       (pad_w//2, pad_w - pad_w//2)), mode="edge")
        h, w = a.shape
    y0 = (h - out_axial_px) // 2
    x0 = (w - out_lateral_px) // 2
    return a[y0:y0+out_axial_px, x0:x0+out_lateral_px]

def center_crop_pad_3d(v: np.ndarray, out_axial_px: int, out_lateral_px: int, out_slices: int) -> np.ndarray:
    z, x, y = v.shape
    pad_z = max(0, out_axial_px - z)
    pad_x = max(0, out_lateral_px - x)
    pad_y = max(0, out_slices - y)
    if pad_z or pad_x or pad_y:
        v = np.pad(v,
                   ((pad_z//2, pad_z - pad_z//2),
                    (pad_x//2, pad_x - pad_x//2),
                    (pad_y//2, pad_y - pad_y//2)),
                   mode="edge")
        z, x, y = v.shape
    z0 = (z - out_axial_px) // 2
    x0 = (x - out_lateral_px) // 2
    y0 = (y - out_slices) // 2
    return v[z0:z0+out_axial_px, x0:x0+out_lateral_px, y0:y0+out_slices]
