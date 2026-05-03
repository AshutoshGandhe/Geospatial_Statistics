"""Generate the four mini-project notebooks (no ERA5; uses pre-processed Excel input).

    python3 gen_notebooks.py

emits notebooks/01_load_uscrn.ipynb ... 04_stats_seasonality.ipynb.
"""
from __future__ import annotations
import json
from pathlib import Path

OUT = Path(__file__).parent / "notebooks"
OUT.mkdir(exist_ok=True)


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def write_nb(name: str, cells: list[dict]) -> None:
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (OUT / name).write_text(json.dumps(nb, indent=1))
    print("wrote", OUT / name)


# ---------------------------------------------------------------------------
# 01 — Load USCRN Excel files into a tidy CSV
# ---------------------------------------------------------------------------
nb1 = [
    md("""# 01 — Load USCRN Excel files into a tidy CSV

You should have the following files in `../data/uscrn/`:
- `All_CONUS_Station_Information*.xlsx`  (station metadata: id, lat, lon)
- `USCRN_Precipitation*.xlsx`
- `USCRN_AirTemperature*.xlsx`
- `USCRN_RelativeHumidity*.xlsx`
- `USCRN_SoilTemperature*.xlsx`
- `USCRN_SoilMoisture*.xlsx`

This notebook is **defensive**: it inspects the workbooks first, then runs a
flexible parser. If your layout differs from the assumed one (date column +
one column per station), the inspection cells show you exactly what to tweak.

Output: `../data/uscrn/uscrn_daily_tidy.csv` with columns
`station_id, lon, lat, date, precip, rh, t_air, t_soil, sm`.
"""),
    code("""import sys, pathlib, glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = pathlib.Path('..').resolve()
sys.path.insert(0, str(ROOT))
from utils import CONUS_BBOX, ensure_dirs, find_col

ensure_dirs(ROOT)
DATA = ROOT / 'data' / 'uscrn'
TIDY = DATA / 'uscrn_daily_tidy.csv'
print('looking in', DATA)
print(sorted(p.name for p in DATA.glob('*.xlsx')))
"""),
    md("## Config"),
    code("""YEAR = 2020   # the year you'll grid in notebooks 02-04. Pick one inside 2006-2021.

# File patterns. Adjust if your filenames differ.
PATTERNS = {
    'station_info': 'All_*Station*Info*.xlsx',
    'precip':       'USCRN_*Precip*.xlsx',
    'rh':           'USCRN_*RelativeHum*.xlsx',
    't_air':        'USCRN_*AirTemp*.xlsx',
    't_soil':       'USCRN_*SoilTemp*.xlsx',
    'sm':           'USCRN_*SoilMoist*.xlsx',
}

paths = {}
for key, pat in PATTERNS.items():
    matches = sorted(DATA.glob(pat))
    assert matches, f'no file matching {pat} in {DATA}'
    paths[key] = matches[0]
    print(f'{key:14s} -> {matches[0].name}')
"""),
    md("## Step 1 — Inspect station info"),
    code("""si_raw = pd.read_excel(paths['station_info'], sheet_name=None)
print('sheets:', list(si_raw.keys()))
si = si_raw[list(si_raw.keys())[0]]
print('shape:', si.shape)
print('columns:', si.columns.tolist())
si.head()
"""),
    code("""# Try to auto-detect station-id, lat, lon columns. Override manually if mis-detected.
ID_COL  = find_col(si.columns, 'station name', 'name', 'wban', 'station id', 'station_id', 'station number', 'location', 'id')
LAT_COL = find_col(si.columns, 'latitude', 'lat')
LON_COL = find_col(si.columns, 'longitude', 'lon')
print('ID  ->', ID_COL)
print('LAT ->', LAT_COL)
print('LON ->', LON_COL)
assert ID_COL and LAT_COL and LON_COL, 'override these manually if auto-detection failed'

station_lookup = (si[[ID_COL, LAT_COL, LON_COL]]
                  .rename(columns={ID_COL: 'station_id', LAT_COL: 'lat', LON_COL: 'lon'})
                  .dropna(subset=['lat', 'lon'])
                  .drop_duplicates('station_id'))
station_lookup['station_id'] = station_lookup['station_id'].astype(str).str.strip()
print('stations with coords:', len(station_lookup))
station_lookup.head()
"""),
    md("## Step 2 — Inspect one variable file"),
    code("""sample = pd.read_excel(paths['precip'], sheet_name=None)
print('sheets:', list(sample.keys()))
df0 = sample[list(sample.keys())[0]]
print('shape:', df0.shape)
print('first 8 columns:', df0.columns[:8].tolist())
df0.head()
"""),
    md("""## Step 3 — Parse a variable workbook

Assumed layout: one column is a date, every other column is a station identifier.
The parser melts to long format and joins station coordinates.
"""),
    code("""def parse_var_file(path, value_col, station_lookup):
    sheets = pd.read_excel(path, sheet_name=None)
    # use the largest sheet
    name = max(sheets, key=lambda k: sheets[k].shape[0] * sheets[k].shape[1])
    df = sheets[name].copy()

    date_col = find_col(df.columns, 'date', 'time')
    if date_col is None:
        date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    df = df.dropna(subset=[date_col])

    long = df.melt(id_vars=[date_col], var_name='station_id', value_name=value_col)
    long = long.rename(columns={date_col: 'date'})
    long['station_id'] = long['station_id'].astype(str).str.strip()
    long = long.dropna(subset=[value_col])

    # numeric coercion (some files have stray strings)
    long[value_col] = pd.to_numeric(long[value_col], errors='coerce')
    long = long.dropna(subset=[value_col])

    merged = long.merge(station_lookup, on='station_id', how='left')
    n_match = merged['lat'].notna().sum()
    n_total = len(merged)
    n_miss_st = merged.loc[merged['lat'].isna(), 'station_id'].nunique()
    print(f'  {value_col:6s}: rows {n_total:>7d}  matched {n_match:>7d}  unmatched stations {n_miss_st}')
    if n_miss_st:
        print('  first 10 unmatched ids:',
              merged.loc[merged['lat'].isna(), 'station_id'].unique()[:10])
    return merged.dropna(subset=['lat', 'lon'])
"""),
    md("## Step 4 — Process all five variables, merge, save"),
    code("""parts = []
for var in ['precip', 'rh', 't_air', 't_soil', 'sm']:
    parts.append(parse_var_file(paths[var], var, station_lookup))

# Merge all variables on (station_id, date, lat, lon)
keys = ['station_id', 'date', 'lat', 'lon']
tidy = parts[0][keys + ['precip']]
for p, var in zip(parts[1:], ['rh', 't_air', 't_soil', 'sm']):
    tidy = tidy.merge(p[keys + [var]], on=keys, how='outer')
print('merged tidy:', tidy.shape)
tidy.head()
"""),
    code("""# Filter to YEAR + CONUS bbox
lonmin, lonmax, latmin, latmax = CONUS_BBOX
mask = (
    tidy['lon'].between(lonmin, lonmax) &
    tidy['lat'].between(latmin, latmax) &
    (tidy['date'].dt.year == YEAR)
)
tidy = tidy.loc[mask].sort_values(['date', 'station_id']).reset_index(drop=True)
print(f'rows in {YEAR} CONUS: {len(tidy)}, stations: {tidy["station_id"].nunique()}')
tidy.to_csv(TIDY, index=False)
print('wrote', TIDY)
"""),
    md("## QC"),
    code("""fig, ax = plt.subplots(figsize=(9, 5))
stations = tidy.groupby('station_id')[['lon', 'lat']].first()
ax.scatter(stations['lon'], stations['lat'], s=18)
ax.set_xlim(lonmin, lonmax); ax.set_ylim(latmin, latmax)
ax.set_title(f'USCRN stations active in {YEAR} (n={len(stations)})')
ax.set_xlabel('lon'); ax.set_ylabel('lat')
plt.show()
"""),
    code("""missing = tidy[['precip','rh','t_air','t_soil','sm']].isna().mean().mul(100).round(1)
print('% missing per variable:'); print(missing)

fig, axes = plt.subplots(1, 5, figsize=(18, 3))
for ax, var in zip(axes, ['precip','rh','t_air','t_soil','sm']):
    tidy[var].dropna().hist(bins=60, ax=ax)
    ax.set_title(var)
plt.tight_layout(); plt.show()
"""),
]

# ---------------------------------------------------------------------------
# 02 — Interpolate to 2-deg grid
# ---------------------------------------------------------------------------
nb2 = [
    md("""# 02 — Interpolate USCRN to a 2-degree CONUS grid

For each day and variable, fit:
- IDW (baseline)
- Ordinary Kriging with **spherical**, **exponential**, **gaussian** variograms

Output: one NetCDF per variable with dims `(time, lat, lon, model)`.

Runtime: ~365 days x 5 vars x 3 OK fits ~= 5500 fits at <0.5 s each
(~30 min on a laptop). IDW is essentially free.
"""),
    code("""import sys, pathlib, warnings
import numpy as np
import pandas as pd
import xarray as xr
from tqdm.auto import tqdm
from pykrige.ok import OrdinaryKriging

warnings.filterwarnings('ignore')

ROOT = pathlib.Path('..').resolve()
sys.path.insert(0, str(ROOT))
from utils import target_grid, ensure_dirs

ensure_dirs(ROOT)
TIDY = ROOT / 'data' / 'uscrn' / 'uscrn_daily_tidy.csv'
GRIDS = ROOT / 'grids'
"""),
    code("""lon_c, lat_c = target_grid()
LONG, LATG = np.meshgrid(lon_c, lat_c)
print('grid shape:', LATG.shape)

df = pd.read_csv(TIDY, parse_dates=['date'])
print('rows:', len(df), '| stations:', df['station_id'].nunique())
"""),
    md("## Interpolation kernels"),
    code("""def idw(x, y, v, xg, yg, power=2, eps=1e-9):
    xg = xg.ravel(); yg = yg.ravel()
    d = np.sqrt((xg[:, None] - x[None, :]) ** 2 + (yg[:, None] - y[None, :]) ** 2)
    w = 1.0 / (d ** power + eps)
    return ((w * v[None, :]).sum(axis=1) / w.sum(axis=1)).reshape(LONG.shape)

def ok_grid(x, y, v, xg, yg, model):
    OK = OrdinaryKriging(
        x, y, v, variogram_model=model,
        verbose=False, enable_plotting=False,
        nlags=12, weight=True,
    )
    z, _ = OK.execute('grid', xg, yg)
    return np.asarray(z)
"""),
    md("## Daily loop"),
    code("""VARS = ['precip', 'rh', 't_air', 't_soil', 'sm']
MODELS = ['idw', 'spherical', 'exponential', 'gaussian']
MIN_STATIONS = 20

dates = pd.date_range(df['date'].min(), df['date'].max(), freq='D')

def grid_one_day(sub, model):
    x = sub['lon'].values; y = sub['lat'].values; v = sub['val'].values
    if model == 'idw':
        return idw(x, y, v, LONG, LATG)
    try:
        return ok_grid(x, y, v, lon_c, lat_c, model)
    except Exception:
        return np.full(LONG.shape, np.nan)

for var in VARS:
    arr = np.full((len(dates), len(lat_c), len(lon_c), len(MODELS)), np.nan, dtype=np.float32)
    for ti, d in enumerate(tqdm(dates, desc=var)):
        sub = df.loc[df['date'] == d, ['lon', 'lat', var]].dropna()
        if len(sub) < MIN_STATIONS:
            continue
        sub = sub.rename(columns={var: 'val'})
        for mi, m in enumerate(MODELS):
            arr[ti, :, :, mi] = grid_one_day(sub, m)
    ds = xr.Dataset(
        {var: (('time', 'lat', 'lon', 'model'), arr)},
        coords={'time': dates, 'lat': lat_c, 'lon': lon_c, 'model': MODELS},
        attrs={'description': f'USCRN-derived {var} on 2-deg CONUS grid'},
    )
    out = GRIDS / f'uscrn_grid_2deg_{var}.nc'
    ds.to_netcdf(out)
    print('wrote', out)
"""),
]

# ---------------------------------------------------------------------------
# 03 — Cross-validation evaluation (no ERA5)
# ---------------------------------------------------------------------------
nb3 = [
    md("""# 03 — Cross-validation evaluation (substitute for ERA5)

Per-day **80/20 holdout cross-validation** at the station level: fit each
interpolation model on 80% of stations, predict at the held-out 20%, and
accumulate observed/predicted pairs across all evaluation dates. This is the
standard internal-validation approach for gridded climate products
(e.g., Hofstra et al., 2008) and substitutes for the missing ERA5 comparison.

Outputs:
- `figs/cv_table.csv`  — pooled RMSE & Pearson r per (variable, model)
- `figs/cv_per_station_<var>.csv` — per-station RMSE
- `figs/cv_map_<var>.png` — bubble map of per-station RMSE
- `figs/best_model_per_variable.csv` — recommendation
"""),
    code("""import sys, pathlib, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm.auto import tqdm
from pykrige.ok import OrdinaryKriging

warnings.filterwarnings('ignore')

ROOT = pathlib.Path('..').resolve()
sys.path.insert(0, str(ROOT))
from utils import CONUS_BBOX

TIDY = ROOT / 'data' / 'uscrn' / 'uscrn_daily_tidy.csv'
FIGS = ROOT / 'figs'; FIGS.mkdir(exist_ok=True)

df = pd.read_csv(TIDY, parse_dates=['date'])
print('rows:', len(df), '| stations:', df['station_id'].nunique())
"""),
    md("## CV kernels (point predictions)"),
    code("""def idw_points(x, y, v, xq, yq, power=2, eps=1e-9):
    d = np.sqrt((xq[:, None] - x[None, :]) ** 2 + (yq[:, None] - y[None, :]) ** 2)
    w = 1.0 / (d ** power + eps)
    return (w * v[None, :]).sum(axis=1) / w.sum(axis=1)

def ok_points(x, y, v, xq, yq, model):
    OK = OrdinaryKriging(
        x, y, v, variogram_model=model,
        verbose=False, enable_plotting=False,
        nlags=12, weight=True,
    )
    z, _ = OK.execute('points', xq, yq)
    return np.asarray(z)
"""),
    md("## 80/20 holdout CV per day"),
    code("""VARS = ['precip', 'rh', 't_air', 't_soil', 'sm']
MODELS = ['idw', 'spherical', 'exponential', 'gaussian']
HOLDOUT_FRAC = 0.2
MIN_STATIONS = 20
SEED = 42

records = []  # one row per (date, model, station, var)

for var in VARS:
    sub_all = df[['date', 'station_id', 'lon', 'lat', var]].dropna()
    sub_all = sub_all.rename(columns={var: 'val'})
    dates = sorted(sub_all['date'].unique())
    rng = np.random.default_rng(SEED)
    for d in tqdm(dates, desc=var):
        sub = sub_all.loc[sub_all['date'] == d]
        if len(sub) < MIN_STATIONS:
            continue
        idx = np.arange(len(sub)); rng.shuffle(idx)
        n_hold = max(1, int(round(HOLDOUT_FRAC * len(idx))))
        hold_i = idx[:n_hold]; train_i = idx[n_hold:]
        train = sub.iloc[train_i]; hold = sub.iloc[hold_i]
        xt, yt, vt = train['lon'].values, train['lat'].values, train['val'].values
        xh, yh, vh = hold['lon'].values, hold['lat'].values, hold['val'].values
        sids = hold['station_id'].values
        for m in MODELS:
            try:
                pred = idw_points(xt, yt, vt, xh, yh) if m == 'idw' \\
                       else ok_points(xt, yt, vt, xh, yh, m)
            except Exception:
                pred = np.full_like(vh, np.nan, dtype=float)
            for sid, obs, p in zip(sids, vh, pred):
                records.append((var, m, str(d.date()), sid, obs, p))

cv = pd.DataFrame.from_records(records, columns=['variable','model','date','station_id','obs','pred'])
cv = cv.dropna()
print('cv rows:', len(cv))
cv.head()
"""),
    md("## Pooled RMSE + Pearson r"),
    code("""def rmse(a, b): return float(np.sqrt(np.mean((a - b) ** 2)))
def pearson(a, b):
    if a.size < 5: return np.nan
    return float(np.corrcoef(a, b)[0, 1])

pooled = (cv.groupby(['variable', 'model'])
            .apply(lambda g: pd.Series({
                'n': len(g),
                'rmse': rmse(g['pred'].values, g['obs'].values),
                'pearson_r': pearson(g['pred'].values, g['obs'].values),
            }))
            .reset_index())
pooled.to_csv(FIGS / 'cv_table.csv', index=False)
pooled
"""),
    code("""best = pooled.loc[pooled.groupby('variable')['rmse'].idxmin()].reset_index(drop=True)
best.to_csv(FIGS / 'best_model_per_variable.csv', index=False)
best
"""),
    md("## Per-station RMSE + bubble map"),
    code("""station_xy = df.groupby('station_id')[['lon', 'lat']].first()

for var in VARS:
    sub = cv[cv['variable'] == var]
    per = (sub.groupby(['station_id', 'model'])
              .apply(lambda g: rmse(g['pred'].values, g['obs'].values))
              .unstack('model'))
    per = per.join(station_xy)
    per.to_csv(FIGS / f'cv_per_station_{var}.csv')

    fig, axes = plt.subplots(1, 4, figsize=(16, 3.5), constrained_layout=True)
    for ax, m in zip(axes, MODELS):
        s = ax.scatter(per['lon'], per['lat'], c=per[m], s=22, cmap='viridis')
        ax.set_title(f'{var} | {m} | per-station RMSE')
        ax.set_xlim(*CONUS_BBOX[:2]); ax.set_ylim(*CONUS_BBOX[2:])
        plt.colorbar(s, ax=ax)
    fig.savefig(FIGS / f'cv_map_{var}.png', dpi=120)
    plt.show()
"""),
]

# ---------------------------------------------------------------------------
# 04 — Statistical assessment + seasonality
# ---------------------------------------------------------------------------
nb4 = [
    md("""# 04 — Statistical assessment + seasonality

- Central tendency (mean, median) and dispersion (variance, std, IQR) per
  (variable, interpolation model) on the 2-deg grid.
- **Pairwise** Kolmogorov-Smirnov 2-sample test between models per variable
  (without ERA5 we compare the gridded distributions to each other).
- Seasonal climatology maps for the **best** model per variable
  (best = lowest CV RMSE from notebook 03).
"""),
    code("""import sys, pathlib
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from itertools import combinations
from scipy.stats import ks_2samp

ROOT = pathlib.Path('..').resolve()
sys.path.insert(0, str(ROOT))
from utils import target_grid

GRIDS = ROOT / 'grids'
FIGS = ROOT / 'figs'; FIGS.mkdir(exist_ok=True)

lon_c, lat_c = target_grid()
VARS = ['precip', 'rh', 't_air', 't_soil', 'sm']
MODELS = ['idw', 'spherical', 'exponential', 'gaussian']
"""),
    md("## Central tendency + dispersion"),
    code("""rows = []
for var in VARS:
    g = xr.open_dataset(GRIDS / f'uscrn_grid_2deg_{var}.nc')[var]
    for m in MODELS:
        x = g.sel(model=m).values.ravel()
        x = x[np.isfinite(x)]
        if x.size == 0:
            continue
        rows.append({
            'variable': var, 'model': m, 'n': int(x.size),
            'mean':   float(np.mean(x)),
            'median': float(np.median(x)),
            'var':    float(np.var(x)),
            'std':    float(np.std(x)),
            'iqr':    float(np.subtract(*np.percentile(x, [75, 25]))),
        })

stats = pd.DataFrame(rows)
stats.to_csv(FIGS / 'central_dispersion.csv', index=False)
stats
"""),
    md("""## Pairwise KS two-sample test

For each variable, run the KS-2sample between every pair of models on the
gridded daily values. Small D and large p-value -> distributions are similar.
"""),
    code("""rng = np.random.default_rng(0)
ks_rows = []
for var in VARS:
    g = xr.open_dataset(GRIDS / f'uscrn_grid_2deg_{var}.nc')[var]
    samples = {}
    for m in MODELS:
        x = g.sel(model=m).values.ravel(); x = x[np.isfinite(x)]
        if x.size == 0:
            continue
        n = min(x.size, 50_000)
        samples[m] = rng.choice(x, n, replace=False)
    for a, b in combinations(samples.keys(), 2):
        D, p = ks_2samp(samples[a], samples[b])
        ks_rows.append({'variable': var, 'model_a': a, 'model_b': b,
                        'ks_D': float(D), 'p_value': float(p)})

ks = pd.DataFrame(ks_rows)
ks.to_csv(FIGS / 'ks_pairwise.csv', index=False)
ks
"""),
    md("## Seasonal climatology (best model per variable)"),
    code("""best = pd.read_csv(FIGS / 'best_model_per_variable.csv').set_index('variable')['model'].to_dict()
SEASONS = {'DJF': [12, 1, 2], 'MAM': [3, 4, 5], 'JJA': [6, 7, 8], 'SON': [9, 10, 11]}

for var in VARS:
    m = best.get(var, 'spherical')
    g = xr.open_dataset(GRIDS / f'uscrn_grid_2deg_{var}.nc')[var].sel(model=m)
    fig, axes = plt.subplots(1, 4, figsize=(16, 3.5), constrained_layout=True)
    for ax, (label, months) in zip(axes, SEASONS.items()):
        season_mean = g.where(g['time.month'].isin(months)).mean('time')
        im = ax.pcolormesh(lon_c, lat_c, season_mean, shading='auto')
        ax.set_title(f'{var} | {label} | {m}')
        plt.colorbar(im, ax=ax)
    fig.suptitle(f'Seasonal climatology — {var} (best model: {m})')
    fig.savefig(FIGS / f'seasonal_{var}.png', dpi=120)
    plt.show()
"""),
    md("## Recommended interpolation model per variable"),
    code("""print(pd.read_csv(FIGS / 'best_model_per_variable.csv').to_string(index=False))
"""),
]


def main() -> None:
    write_nb("01_load_uscrn.ipynb", nb1)
    write_nb("02_interpolate.ipynb", nb2)
    write_nb("03_evaluate_cv.ipynb", nb3)
    write_nb("04_stats_seasonality.ipynb", nb4)


if __name__ == "__main__":
    main()
