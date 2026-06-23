# Urban Heat Island GeoAI — Tel Aviv

**🗺️ [Live interactive app](https://green-walls-for-heat-islands-tlv.streamlit.app/)** | **[GitHub repo](https://github.com/omerbu604/Green-walls-for-heat-islands)**

> **Proof of concept** — built as part of the GeoAI course at Arena.  
> The pipeline demonstrates that spatial AI can prioritize green wall interventions at city scale. It does not account for all real-world parameters (wall materials, irrigation, plant species, legal constraints).

---

## Problem

Dense urban neighbourhoods become significantly hotter than vegetated areas — the **Urban Heat Island (UHI)** effect. Municipalities lack actionable tools to answer:

- Where are the worst heat hotspots in the city?
- What urban characteristics (density, vegetation, proximity to roads) drive high temperatures?
- Which buildings should receive green walls first?
- Given a fixed budget, where does the city get the most cooling per shekel?

### Why this is a GeoAI problem

Every part of the pipeline is inherently spatial:

| Spatial element | How it appears in this project |
|---|---|
| **Raster layers** | Satellite-derived NDVI (10 m) and LST (30 m) cover the entire city as continuous grids |
| **Vector layers** | Building footprints, road network, water bodies — all georeferenced polygons/lines |
| **Coordinate system** | All metric operations in EPSG:2039 (Israel TM Grid); visualisation in EPSG:4326 |
| **Spatial grid** | 100 × 100 m fishnet clipped to the municipal boundary — the unit of analysis |
| **Distance calculations** | `dist_major_road`, `dist_to_water` computed via nearest-neighbour spatial join |
| **Zonal statistics** | Raster values (NDVI, LST) aggregated per grid cell via `rasterstats` |
| **Spatial join** | Building footprints overlaid onto the grid to derive built-up % and mean height |
| **Hotspot detection** | Top-20% heat-priority cells identified spatially across the city |
| **Spatial prediction** | XGBoost model predicts LST *at each grid location* from its spatial context |
| **Prescriptive spatial output** | Green wall recommendations mapped per building, budget-optimised |

---

## Data Sources

| Layer | Source | Format | Records / Resolution |
|---|---|---|---|
| Land Surface Temperature (LST) | Landsat 8 + 9 Collection 2 L2 via GEE | GeoTIFF | 30 m · 12-month median & P90 |
| NDVI | Sentinel-2 SR Harmonised via GEE | GeoTIFF | 10 m · single cloud-free scene |
| Building footprints + heights | Tel Aviv municipality open data | GeoJSON (EPSG:2039) | **25,818 polygons** |
| Municipal boundary | Tel Aviv open data | GeoJSON (EPSG:4326) | 1 polygon |
| Road network | OpenStreetMap (Geofabrik) | Shapefile → GeoJSON | **2,572 road segments** (primary / secondary / tertiary / trunk / motorway) |
| Water bodies | OpenStreetMap (Geofabrik) | Shapefile → GeoJSON | **94 polygons** (sea coast, Yarkon river, ponds) |

**Analysis grid:** 5,080 valid 100 × 100 m cells after clipping to the city boundary and removing invalid coastal cells.

---

## Data Preparation

### Satellite data (Google Earth Engine — Colab)

- **Cloud masking:** Sentinel-2 SCL band (Scene Classification Layer) to remove clouds and shadows; Landsat QA_PIXEL bitmask for the same purpose
- **Composite:** 12-month median and 90th-percentile LST composites from merged Landsat 8 + 9 scenes (not a single image) — reduces cloud contamination and seasonal noise
- **LST conversion:** `ST_B10 × 0.00341802 + 149.0 − 273.15 = °C` (Landsat Collection 2 L2 scale factor)
- **Nodata issue fixed:** GEE exported the LST raster without a nodata tag — coastal/sea pixels were stored as `0 °C` instead of `NaN`. This caused 354 grid cells with `mean_LST = 0`, which inflated the model R² to 0.97 (a false result). Fixed by filtering `mean_LST > 5 °C` before training.

### Grid feature engineering (local — GeoPandas / rasterstats)

| Feature | Method |
|---|---|
| `mean_NDVI`, `mean_LST` | `rasterstats.zonal_stats` — mean raster value per grid cell |
| `pct_green` | Fraction of 10 m NDVI pixels > 0.3 per cell (no external land-cover layer needed) |
| `pct_built` | `gpd.overlay` — building footprint area intersecting cell ÷ cell area |
| `mean_building_height` | Area-weighted mean height from building fragments per cell |
| `building_density` | Count of unique buildings touching each cell |
| `dist_major_road` | `gpd.sjoin_nearest` — centroid to nearest major road segment |
| `dist_to_water` | `gpd.sjoin_nearest` — centroid to nearest water body |

**Spatial join rule:** always `how="left"` so every grid cell is retained even if no buildings overlap.  
**CRS rule:** all distance and area operations in EPSG:2039; reprojected to EPSG:4326 only for visualisation and raster sampling.

---

## Machine Learning

### Model: LST Regression (supervised)

**Target (y):** `mean_LST` per 100 × 100 m grid cell  
**Features (X):** `mean_NDVI`, `pct_green`, `pct_built`, `mean_building_height`, `building_density`, `dist_major_road`, `dist_to_water`

Three models compared on an 80/20 train–test split:

| Model | R² (full features) | R² (morphology only — no NDVI) |
|---|---|---|
| Linear Regression | 0.24 | 0.08 |
| Random Forest | 0.38 | 0.19 |
| **XGBoost** | **0.41** | **0.21** |

Two versions were trained intentionally:
- **Full model (with NDVI):** NDVI is the strongest predictor (~35% importance) — vegetation is the dominant cooling mechanism
- **Morphology-only model (without NDVI):** isolates the contribution of urban structure (built-up %, road proximity) to heat independently of current vegetation

### Scenario Simulation

After training, the XGBoost model is used for **green wall impact prediction**:
1. Estimate the NDVI increase that green walls on surrounding buildings would add to each grid cell
2. Re-predict LST with the modified NDVI input
3. `predicted_cooling = baseline_LST − simulated_LST` (clipped ≥ 0)

This gives a model-estimated cooling value per grid cell that feeds into the building scoring.

---

## Analytics Stages Reached

### 1 — Descriptive
- Heat priority score per grid cell: `norm(LST) × (1 − norm(NDVI)) × built_up_score × road_exposure_score`
- Hotspot map: top 20% cells by heat priority flagged as urban heat islands
- Feature importance charts explaining which urban characteristics drive high LST

### 2 — Predictive
- XGBoost regression model predicts LST from urban morphology (R² = 0.41)
- Scenario simulation: model predicts LST drop from increased NDVI due to green walls

### 3 — Prescriptive
Each of the 25,818 buildings receives a **green wall score (1–10)**:

```
eligible_wall_area = perimeter × height × coverage_ratio (0.4)

green_wall_score = heat_priority_nearby
                 × eligible_wall_area
                 × sun_exposure_score
                 × exp(−dist_to_hotspot / 300 m)
                 × predicted_cooling
```

**Sun exposure score:** computed from the outward-facing bearing of each wall segment. South-facing walls (bearing 180°) score 1.0; north-facing score 0.0. Buildings with a taller neighbour within 25 m to the south receive a shade penalty.

**Budget optimizer:** buildings ranked by `score / cost` (cost = `eligible_wall_area × ₪1,500/m²`). Greedy selection picks buildings in rank order until the budget is exhausted — tested at ₪5M / ₪20M / ₪50M.

---

## Project Structure

```
notebooks/
  01_ndvi_sentinel2_gee.ipynb     # Sentinel-2 NDVI via GEE (Colab)
  02_lst_landsat_gee.ipynb        # Landsat LST median + P90 via GEE (Colab)
  03_grid_features.ipynb          # 100×100 m grid + all spatial features
  04_modeling.ipynb               # XGBoost LST model + scenario simulation
  05_green_wall_scoring.ipynb     # Building scores + budget optimizer
app/
  streamlit_app.py                # Interactive Streamlit + Folium map
Layers/                           # Source data (rasters, vectors)
outputs/                          # Generated GeoPackages, models, figures
```

---

## Technical Stack

- **Google Earth Engine** — satellite composites (Colab notebooks)
- **GeoPandas · rasterio · rasterstats** — spatial feature engineering
- **scikit-learn · XGBoost** — regression model
- **Streamlit · Folium · branca** — interactive map app
- **EPSG:2039** for all metric operations; **EPSG:4326** for visualisation

---

## Limitations

- LST measured at ~10:30 local time (Landsat overpass) — daytime surface temperature, not air temperature
- Green wall cooling impact is model-estimated, not physically simulated
- Sun/shade analysis uses 2D building footprints — ignores non-building obstructions
- Budget optimizer uses a fixed assumed cost per m² — real costs vary by building type and access
- A single NDVI scene (2026-05-29) is used — seasonal variation not captured
