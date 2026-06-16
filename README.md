# Urban Heat Island GeoAI — Tel Aviv

Detect urban heat hotspots and rank buildings for **green wall** intervention using satellite imagery and spatial analysis.

🗺️ **[Live interactive map](https://green-walls-for-heat-islands-tlv.streamlit.app/)** | **[GitHub repo](https://github.com/omerbu604/Green-walls-for-heat-islands)**

> **Proof of concept** built as part of the GeoAI course at Arena. The pipeline demonstrates that spatial AI can prioritize green infrastructure at city scale — it does not account for all real-world parameters (wall materials, irrigation, plant species, legal constraints, microclimate effects).

---

## Problem

Dense urban areas become significantly hotter than vegetated zones — the **Urban Heat Island (UHI)** effect. Municipalities and planners often lack actionable tools to answer:

- Where are the worst heat hotspots?
- Which urban characteristics drive high temperatures?
- Which buildings should be prioritized for green infrastructure?
- Given a fixed budget, where should the city invest first?

> **Core question:** In which areas and buildings in Tel Aviv should green walls be prioritized to reduce urban heat stress?

---

## Approach

The project has three layers:

### 1 — Hotspot Scoring
A **100 × 100 m urban grid** where each cell is scored by heat priority:

```text
heat_priority = norm(LST) × (1 - norm(NDVI)) × built_up_score × road_exposure_score
```

### 2 — GeoAI Model
A **regression model** trained to predict LST from urban morphology features (NDVI, building density, height, built-up %, road proximity, distance to water). Used for **scenario simulation** — given a green wall intervention, predict the resulting LST drop.

### 3 — Green Wall Ranking
Each building receives a score (1–10) combining:

```text
eligible_wall_area = building_perimeter × building_height × coverage_ratio

green_wall_score = heat_priority_nearby
                 × eligible_wall_area
                 × sun_exposure_score      # wall orientation + shade obstruction
                 × exp(-distance / 300)    # distance decay to nearest hot cell
                 × predicted_lst_impact    # model-predicted temperature reduction
```

**Sun exposure score** accounts for wall orientation (south-facing = max sun in Israel) and shade obstruction from adjacent taller buildings to the south.

### 4 — Budget Optimizer
City planners input a budget. Each building has an estimated cost (`eligible_wall_area × cost_per_m²`). Buildings are ranked by `score / cost` ratio and selected greedily until the budget is exhausted.

---

## Data Layers

| File | CRS | Contents |
|---|---|---|
| `Layers/tel_aviv_buildings_only_ITM.geojson` | EPSG:2039 | 25,818 building polygons, `id` + `height` (m) |
| `Layers/tel_aviv_border.geojson` | EPSG:4326 | Tel Aviv municipal boundary |
| `Layers/tel_aviv_ndvi_2026-05-29.tif` | EPSG:4326 | NDVI at 10 m (Sentinel-2, single scene) |
| `Layers/tel_aviv_lst_median.tif` | EPSG:4326 | LST median °C at 30 m (Landsat 8/9, 12-month) |
| `Layers/tel_aviv_lst_p90.tif` | EPSG:4326 | LST 90th-percentile °C at 30 m (Landsat 8/9, 12-month) |
| `Layers/osm/gis_osm_roads_free_1.shp` | EPSG:4326 | Road network — filter to primary/secondary/tertiary/trunk/motorway |
| `Layers/osm/gis_osm_water_a_free_1.shp` | EPSG:4326 | Water bodies (sea, Yarkon river) — used for distance-to-water feature |

> OSM traffic layers (`traffic_a`, `traffic`) are present but not used — road proximity and NDVI already capture the relevant signals.

---

## Grid Features

| Feature | Source | Role |
|---|---|---|
| `mean_LST` | Landsat raster | Model target (y) |
| `mean_NDVI` | Sentinel-2 raster | Model feature + green score |
| `pct_built` | Buildings footprint / cell area | Model feature |
| `mean_building_height` | Buildings layer | Model feature |
| `building_density` | Buildings count / cell | Model feature |
| `dist_major_road` | OSM roads (filtered) | Model feature + exposure score |
| `dist_to_water` | OSM water layer | Model feature (coastal cooling) |

---

## GeoAI Model

**Task:** Regression — predict `mean_LST` per grid cell from the features above (no satellite thermal input).

**Pipeline:** Linear Regression (baseline) → Random Forest → XGBoost  
**Evaluation:** MAE, RMSE, R² on held-out test cells  
**Output:** Feature importance + scenario simulation (predict LST drop from NDVI increase caused by green walls)

---

## Technical Stack

- **GeoPandas / rasterio / rasterstats** — spatial feature engineering
- **scikit-learn / XGBoost** — regression model
- **EPSG:2039** for all metric operations; **EPSG:4326** for visualization
- **Streamlit + Folium** — interactive map with budget slider

---

## Project Structure

```
notebooks/
  01_ndvi_sentinel2_gee.ipynb       # Sentinel-2 NDVI via GEE (done)
  02_lst_landsat_gee.ipynb          # Landsat LST via GEE (done)
  03_grid_features.ipynb            # Grid creation + feature engineering
  04_modeling.ipynb                 # LST regression model
  05_green_wall_scoring.ipynb       # Building scores + budget optimizer
src/
  features.py                       # Grid + zonal stats helpers
  modeling.py                       # Model training + scenario simulation
  scoring.py                        # Green wall + budget optimizer logic
app/
  streamlit_app.py                  # Interactive map
Layers/                             # All source data layers
outputs/                            # Generated maps and figures
```

---

## Success Criteria

- [ ] 100 × 100 m grid covering Tel Aviv (~500+ cells)
- [ ] Trained LST regression model (R² > 0.6 target)
- [ ] Feature importance explaining heat drivers
- [ ] Green wall scores (1–10) for all buildings with sun/shade logic
- [ ] Budget optimizer tested with at least 3 budget scenarios
- [ ] Streamlit app showing all layers + budget slider

---

## Limitations

- LST is measured at ~10:30 local time (Landsat overpass) — daytime surface temperature, not air temperature.
- Green wall LST impact is model-estimated, not physically simulated.
- Sun/shade analysis uses 2D building footprints — does not account for non-building obstructions.
- Budget optimizer uses a fixed assumed cost per m² — real costs vary by building type and access.
