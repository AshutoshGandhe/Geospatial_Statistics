# GNR 640 — Mini Project (USCRN-only path)

Generate 2-degree daily gridded products from USCRN station observations for
five hydroclimatic variables, evaluate via per-day holdout cross-validation,
and assess statistical & seasonal agreement.

> **No ERA5?** This pipeline works without it. We substitute ERA5 comparison
> with **per-day 80/20 holdout cross-validation** at the station level, and
> replace "distributional similarity vs ERA5" with **pairwise KS between
> interpolation models**. State this clearly in your report's Limitations
> section to keep the methodology defensible.

## Layout

```
gnr640_project/
├── requirements.txt
├── utils.py
├── gen_notebooks.py
├── data/uscrn/                    ← drop your 6 .xlsx files here
└── notebooks/
    ├── 01_load_uscrn.ipynb        Excel → tidy CSV (with inspection cells)
    ├── 02_interpolate.ipynb       Tidy CSV → IDW + 3 kriging variograms → 5 NetCDFs
    ├── 03_evaluate_cv.ipynb       Per-day 80/20 holdout CV → RMSE/r tables + maps
    └── 04_stats_seasonality.ipynb Stats, pairwise KS, seasonal climatology
```

The first run of any notebook also creates `grids/` and `figs/`.

## Setup

```bash
cd gnr640_project
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name gnr640 --display-name "Python (gnr640)"
```

## Data placement

Drop these directly into `data/uscrn/`:

```
data/uscrn/
├── All_CONUS_Station_Information....xlsx
├── USCRN_AirTemperature_2006_2021.xlsx
├── USCRN_Precipitation_2006_2021.xlsx
├── USCRN_RelativeHumidity_2006_2021.xlsx
├── USCRN_SoilMoisture10cm_2006_2021.xlsx
└── USCRN_SoilTemperature_2006_2021.xlsx
```

The exact filenames don't matter — notebook 01 globs them. If your filenames
diverge significantly, edit `PATTERNS` in the config cell.

## Run order

```bash
jupyter lab
```

then execute notebooks **in order**:

| # | Notebook | What it does | Outputs |
|---|---|---|---|
| 01 | `01_load_uscrn.ipynb` | Inspect Excel layout, parse all 5 variable workbooks, join to station coordinates, filter to YEAR + CONUS, save tidy CSV. | `data/uscrn/uscrn_daily_tidy.csv` |
| 02 | `02_interpolate.ipynb` | Per-day IDW + Ordinary Kriging (spherical / exponential / gaussian) on the 2-deg grid for each variable. | `grids/uscrn_grid_2deg_<var>.nc` × 5 |
| 03 | `03_evaluate_cv.ipynb` | 80/20 holdout CV per day → pooled RMSE & Pearson r per (variable, model), per-station RMSE bubble maps, best-model recommendation. | `figs/cv_table.csv`, `figs/cv_per_station_<var>.csv`, `figs/cv_map_<var>.png`, `figs/best_model_per_variable.csv` |
| 04 | `04_stats_seasonality.ipynb` | Mean/median/var/std/IQR per (variable, model). Pairwise KS-2sample between models. Seasonal (DJF/MAM/JJA/SON) climatology figures using the best model per variable. | `figs/central_dispersion.csv`, `figs/ks_pairwise.csv`, `figs/seasonal_<var>.png` |

## Knobs

- **Year** — `YEAR = 2020` at the top of notebook 01. Pick any single year inside 2006–2021. Only one year is gridded to keep notebook 02's runtime tractable.
- **Hold-out fraction** — `HOLDOUT_FRAC = 0.2` in notebook 03.
- **Min stations per day** — `MIN_STATIONS = 20` (skips sparsely-observed days).
- **Variogram models** — `MODELS` list in 02 and 03. PyKrige supports `linear`, `power`, `gaussian`, `spherical`, `exponential`, `hole-effect`.
- **Grid / domain** — `target_grid()` and `CONUS_BBOX` in `utils.py`.

## Deliverables checklist (for the report)

- [ ] **Gridded products** — 5 NetCDFs from notebook 02. Upload to Zenodo / figshare for a DOI.
- [ ] **Performance table** — `figs/cv_table.csv` (RMSE & r per variable × model).
- [ ] **Per-station error maps** — `figs/cv_map_<var>.png` × 5.
- [ ] **Statistical summary** — `figs/central_dispersion.csv`.
- [ ] **Distributional similarity** — `figs/ks_pairwise.csv`.
- [ ] **Seasonal climatology** — `figs/seasonal_<var>.png` × 5.
- [ ] **Model recommendation** — `figs/best_model_per_variable.csv`.
- [ ] **Report PDF** — methods, results, figures, and a Limitations paragraph
  explicitly noting (a) ERA5 was unavailable, (b) per-day holdout CV is the
  substitute for objective 2, (c) KS was computed pairwise between
  interpolation models rather than against an external reference.

## Regenerating the notebooks

The notebooks are produced from `gen_notebooks.py`. After tweaking cell sources there:

```bash
python3 gen_notebooks.py
```
