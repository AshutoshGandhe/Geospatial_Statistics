"""Shared helpers for the GNR 640 mini-project notebooks."""
from pathlib import Path
import numpy as np

# CONUS bounding box (lon_min, lon_max, lat_min, lat_max). AK/HI excluded —
# they would leave most of a 2-degree grid empty.
CONUS_BBOX = (-125.0, -66.0, 24.0, 50.0)


def target_grid():
    """Return (lon_centers, lat_centers) for the 2-degree CONUS grid."""
    lon = np.arange(-124.0, -65.0 + 1e-6, 2.0)
    lat = np.arange(25.0, 50.0 + 1e-6, 2.0)
    return lon, lat


def ensure_dirs(root):
    root = Path(root)
    for sub in ["data/uscrn", "grids", "figs"]:
        (root / sub).mkdir(parents=True, exist_ok=True)


def find_col(columns, *candidates):
    """Return the first column whose name contains any candidate (case-insensitive)."""
    for cand in candidates:
        for c in columns:
            if cand.lower() in str(c).lower():
                return c
    return None
