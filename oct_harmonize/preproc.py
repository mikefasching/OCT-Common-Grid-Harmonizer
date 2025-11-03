import numpy as np
from scipy.ndimage import gaussian_filter1d

def maybe_undo_log_gamma(arr: np.ndarray, gamma: float = 1.0):
    """
    Heuristic 'undo log'. Expects input roughly in [0,1].
    If a PNG/JPG was loaded (0..255), normalize first.
    """
    a = arr.astype(np.float32)
    # normalize if it looks like 8-bit
    if np.nanmax(a) > 2.0:
        a = a / 255.0

    a = np.clip(a, 0.0, None)
    a = np.expm1(a)  # inverse of log1p-like compression (heuristic)
    if gamma != 1.0:
        a = np.power(a, 1.0 / gamma)
    # re-normalize to [0,1] for downstream steps
    hi = np.percentile(a, 99.9); lo = np.percentile(a, 0.1)
    return np.zeros_like(a) if hi <= lo else np.clip((a - lo) / (hi - lo), 0.0, 1.0)

def percentile_normalize(arr: np.ndarray, p_low=1.0, p_high=99.0):
    lo = np.percentile(arr, p_low)
    hi = np.percentile(arr, p_high)
    if hi <= lo:
        return np.zeros_like(arr)
    a = (arr - lo) / (hi - lo)
    return np.clip(a, 0.0, 1.0)

def rpe_flatten_stub(arr: np.ndarray, smooth_sigma=3.0):
    """
    Very simple RPE 'flattening' placeholder:
    - Detect bright band near bottom along each column (max over lower half).
    - Shift rows to align that band to a reference row.
    Works on 2D or 3D (applies per-slice).
    Replace with real layer segmentation for production use.
    """
    if arr.ndim == 2:
        return _flatten2d(arr, smooth_sigma)
    elif arr.ndim == 3:
        out = np.empty_like(arr)
        for k in range(arr.shape[2]):  # iterate y/slices
            out[..., k] = _flatten2d(arr[..., k], smooth_sigma)
        return out
    else:
        return arr

def _flatten2d(img: np.ndarray, sigma):
    h, w = img.shape
    start = h // 2
    band_pos = start + np.argmax(img[start:, :], axis=0)  # [w]
    band_pos = gaussian_filter1d(band_pos.astype(np.float32), sigma=sigma)
    ref = int(h * 0.8)
    shifts = (ref - band_pos).astype(int)
    out = np.zeros_like(img)
    for x in range(w):
        s = shifts[x]
        if s >= 0:
            out[s:, x] = img[:h - s, x]
        else:
            s = -s
            out[:h - s, x] = img[s:, x]
    return out
