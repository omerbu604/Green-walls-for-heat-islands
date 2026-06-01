# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Urban Heat Island (UHI) detection and green-wall intervention ranking for Tel Aviv. The pipeline scores **100 × 100 m grid cells** by heat priority and scores individual **buildings** by their green-wall installation potential. See README.md for the full scoring formulas.

## Planned Project Structure

```
notebooks/          # Jupyter notebooks, numbered by pipeline stage
  01_data_collection.ipynb
  02_spatial_features.ipynb
  03_modeling.ipynb
  04_green_wall_scoring.ipynb
src/                # Reusable Python modules called from notebooks
  data_loader.py
  spatial_features.py
  modeling.py
  scoring.py
app/
  streamlit_app.py  # Interactive map (Streamlit + Folium)
Layers/             # Source vector layers (GeoJSON)
outputs/            # Generated maps and figures
```

## CRS Convention

All distance, buffer, and area calculations must use **EPSG:2039** (Israel TM Grid — meters).  
All web visualization and export must use **EPSG:4326** (WGS84).

Never mix CRS within a spatial operation. Always reproject before joining or buffering.

## Existing Data Layers (`Layers/`)

| File | CRS | Contents |
|---|---|---|
| `tel_aviv_buildings_only_ITM.geojson` | EPSG:2039 | 25,818 building polygons with `id` and `height` (metres) attributes |
| `tel_aviv_border.geojson` | WGS84 | Tel Aviv municipal boundary |

Building heights range from 2 m to 270 m. Coverage is near-complete (sourced from GEE).  
The border file is used for clipping all other layers to the study area.

## Key Spatial Patterns

**Grid creation** — create a fishnet of 100 × 100 m cells clipped to the Tel Aviv border. Work in EPSG:2039.

**Spatial join pattern** — always `how="left"` from the grid onto feature layers so every cell is retained even with no intersecting features.

**Buffer-based proximity** — use `geometry.buffer(distance)` + `gpd.sjoin` to replicate PostGIS `ST_DWithin`. Prefer `gpd.sjoin_nearest` with `distance_col` when you only need the nearest feature.

**Heat priority score:**
```
heat_priority = normalized_LST × (1 - normalized_NDVI) × built_up_score × exposure_score
```

**Green wall potential score:**
```
eligible_wall_area = building_perimeter × building_height × coverage_ratio
green_wall_score   = heat_priority_nearby × eligible_wall_area × exp(-distance / 50) × public_exposure_score
```

## Running the Project

```bash
# Notebooks
jupyter notebook

# Streamlit app (once built)
streamlit run app/streamlit_app.py
```

## Satellite Data Sources

- **Landsat** → Land Surface Temperature (LST)
- **Sentinel-2** → NDVI
- **Dynamic World** → land-cover classification (built-up / green / water)

All satellite data is accessed via Google Earth Engine (GEE). Exported layers are stored under `Layers/` or `data/processed/`.
