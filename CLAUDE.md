# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Urban Heat Island (UHI) detection and green-wall intervention ranking for Tel Aviv. The pipeline scores **100 × 100 m grid cells** by heat priority, trains a regression model to predict LST and simulate green wall impact, and ranks individual buildings for green wall installation with a budget optimizer.

## Project Structure

```
notebooks/          # Jupyter notebooks, numbered by pipeline stage
  01_ndvi_sentinel2_gee.ipynb     # done — Sentinel-2 NDVI via GEE
  02_lst_landsat_gee.ipynb        # done — Landsat LST median + P90 via GEE
  03_grid_features.ipynb          # next — grid creation + feature engineering
  04_modeling.ipynb               # LST regression model + scenario simulation
  05_green_wall_scoring.ipynb     # building scores + budget optimizer
src/
  features.py                     # grid creation, zonal stats, spatial join helpers
  modeling.py                     # model training + LST scenario simulation
  scoring.py                      # green wall scoring + budget optimizer
app/
  streamlit_app.py                # Streamlit + Folium interactive map
Layers/                           # all source data (see table below)
outputs/                          # generated maps and figures
```

## CRS Convention

All distance, buffer, area, and grid calculations → **EPSG:2039** (Israel TM Grid, metres).  
All web visualization and GeoTIFF export → **EPSG:4326** (WGS84).  
Never mix CRS within a spatial operation. Always reproject before joining or buffering.

## Data Layers

| File | CRS | Contents |
|---|---|---|
| `Layers/tel_aviv_buildings_only_ITM.geojson` | EPSG:2039 | 25,818 polygons, `id` + `height` (m), heights 2–270 m |
| `Layers/tel_aviv_border.geojson` | EPSG:4326 | Municipal boundary — clip all layers to this |
| `Layers/tel_aviv_ndvi_2026-05-29.tif` | EPSG:4326 | NDVI 10 m, single Sentinel-2 scene |
| `Layers/tel_aviv_lst_median.tif` | EPSG:4326 | LST °C 30 m, 12-month median (Landsat 8/9) |
| `Layers/tel_aviv_lst_p90.tif` | EPSG:4326 | LST °C 30 m, 12-month P90 (Landsat 8/9) |
| `Layers/osm/gis_osm_roads_free_1.shp` | EPSG:4326 | Full road network — **filter fclass to: primary, secondary, tertiary, trunk, motorway** |
| `Layers/osm/gis_osm_water_a_free_1.shp` | EPSG:4326 | Water bodies — used for `dist_to_water` feature |

OSM `traffic_a` and `traffic` layers exist but are not used in the pipeline.

## Grid Feature Engineering

The analysis grid is 100 × 100 m cells clipped to the Tel Aviv border (work in EPSG:2039).

**Raster → grid** (use `rasterstats.zonal_stats`):
- `mean_NDVI` from `tel_aviv_ndvi_2026-05-29.tif`
- `mean_LST` from `tel_aviv_lst_median.tif` (model target)

**Vector → grid** (use `gpd.sjoin` or `gpd.sjoin_nearest`):
- `pct_built` = sum of building footprint area intersecting cell / cell area
- `mean_building_height`, `building_density` = from buildings layer
- `dist_major_road` = `gpd.sjoin_nearest` to filtered roads
- `dist_to_water` = `gpd.sjoin_nearest` to water layer

**Derived:**
- `pct_green` = fraction of pixels where NDVI > 0.3 (no Dynamic World needed)

## ML Model

**Task:** Regression — predict `mean_LST` from all features except `mean_LST`.  
**GEE project ID:** `celtic-house-472106-d1`  
**Scenario simulation:** After training, increase `mean_NDVI` by the delta a green wall would add, re-predict LST → this gives `predicted_lst_impact` per building.

## Spatial Patterns

**Left join always** — `gpd.sjoin(..., how="left")` from grid onto features so every cell is retained.

**Buffer proximity** — `geometry.buffer(d)` + `gpd.sjoin` for range queries. Use `gpd.sjoin_nearest` with `distance_col` when only the nearest feature is needed.

## Green Wall Scoring

```
eligible_wall_area = building_perimeter × building_height × coverage_ratio
sun_score          = cos(wall_bearing - 180°) normalised 0–1, reduced if taller building within ~20 m to south
green_wall_score   = heat_priority_nearby × eligible_wall_area × sun_score
                   × exp(-dist_to_hot_cell / 50) × predicted_lst_impact
```

Score is normalised to 1–10 for the final output.

## Budget Optimizer

Input: total budget (₪).  
Assumed cost: `eligible_wall_area × cost_per_m²` (default ₪1,500/m²).  
Selection: rank buildings by `green_wall_score / cost`, greedily pick until budget exhausted.

## Running the Project

```bash
jupyter notebook          # open any notebook
streamlit run app/streamlit_app.py   # interactive map (once built)
```
