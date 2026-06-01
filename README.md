# Urban Heat Island GeoAI — Tel Aviv

Detect urban heat hotspots and rank buildings for **green wall** intervention using satellite imagery and spatial analysis.

---

## Problem

Dense urban areas become significantly hotter than vegetated zones — the **Urban Heat Island (UHI)** effect. Municipalities and planners often lack actionable tools to answer:

- Where are the worst heat hotspots?
- Which urban characteristics drive high temperatures?
- Which buildings should be prioritized for green infrastructure?

> **Core question:** In which areas and buildings in Tel Aviv should green walls be prioritized to reduce urban heat stress?

---

## Approach

The project builds a spatial scoring pipeline over a **100 × 100 m urban grid**:

1. Compute per-cell features from satellite and vector data.
2. Score each cell with a **Heat Priority Score**.
3. Score each building with a **Green Wall Potential Score**.
4. Expose results through an interactive map.

### Heat Priority Score

```text
heat_priority = normalized_LST × (1 - normalized_NDVI) × built_up_score × exposure_score
```

### Green Wall Potential Score

```text
eligible_wall_area   = building_perimeter × building_height × coverage_ratio
green_wall_score     = heat_priority_nearby × eligible_wall_area × exp(-distance / 50) × public_exposure_score
```

The exponential decay term ensures buildings closer to hot cells score higher.

---

## Data Sources

| Category | Source | Usage |
|---|---|---|
| Land Surface Temperature | Landsat | LST calculation |
| Vegetation index | Sentinel-2 | NDVI |
| Land cover | Dynamic World | Built-up / green / water classification |
| Building footprints & height | Tel Aviv open data | Facade area, density |
| Administrative boundaries | Tel Aviv open data | Study-area clipping |
| Roads, parks, POIs | OpenStreetMap | Distance features, exposure |

---

## Spatial Features per Grid Cell

| Feature | Description |
|---|---|
| `mean_LST` | Average land surface temperature |
| `mean_NDVI` | Average vegetation index |
| `pct_built` | Percentage of built-up/impervious surface |
| `pct_green` | Percentage of green area |
| `mean_building_height` | Average building height |
| `building_density` | Building count per cell |
| `dist_nearest_park` | Distance to nearest park (m) |
| `dist_major_road` | Distance to nearest major road (m) |
| `public_exposure` | Proximity to bus stops, sport facilities, public spaces |

---

## Technical Stack

- **GeoPandas** — vector data loading, spatial joins, buffers, distance calculations
- **EPSG:2039** (Israel TM Grid) for metric operations; **EPSG:4326** for web visualization
- **scikit-learn** — regression or classification model for LST / hotspot prediction
- **Streamlit + Folium** — interactive map application

### CRS workflow

```python
# Metric analysis
buildings = buildings.to_crs(epsg=2039)
grid      = grid.to_crs(epsg=2039)

# Web visualization
grid_web      = grid.to_crs(epsg=4326)
buildings_web = buildings.to_crs(epsg=4326)
```

### Key spatial operations

```python
# Buildings per grid cell
grid_buildings = gpd.sjoin(grid, buildings, how="left", predicate="intersects")

# Buildings near hot cells (buffer-based DWithin)
hot_cells_buffer = grid[grid["heat_priority"] > 0.8].copy()
hot_cells_buffer["geometry"] = hot_cells_buffer.geometry.buffer(100)
near_hot = gpd.sjoin(buildings, hot_cells_buffer, how="inner", predicate="intersects")

# Nearest-park distance
buildings_with_parks = gpd.sjoin_nearest(
    buildings, parks, how="left", distance_col="dist_park"
)
```

---

## GeoAI Model

**Option A — Regression:** Predict LST from spatial features (Linear Regression → Random Forest → XGBoost).

**Option B — Classification:** Classify grid cells as heat hotspot / not (Logistic Regression → Random Forest → Gradient Boosting).

---

## Project Structure

```
urban-heat-green-walls/
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_spatial_features.ipynb
│   ├── 03_modeling.ipynb
│   └── 04_green_wall_scoring.ipynb
├── src/
│   ├── data_loader.py
│   ├── spatial_features.py
│   ├── modeling.py
│   └── scoring.py
├── app/
│   └── streamlit_app.py
├── outputs/
│   ├── maps/
│   └── figures/
├── README.md
└── requirements.txt
```

---

## Success Criteria

- [ ] ≥ 500 spatial grid observations
- [ ] Clear identification of UHI hotspots
- [ ] Baseline predictive/scoring model with documented performance
- [ ] Explainable per-building green wall ranking
- [ ] Interactive map with LST, NDVI, heat-priority, and building-score layers
- [ ] Correct use of CRS, spatial joins, buffers, and distance calculations

---

## Limitations

- LST ≠ pedestrian-level air temperature.
- Satellite data is affected by cloud cover, season, and acquisition time.
- Green wall scores are relative rankings, not physical microclimate simulations.
- Building height data may be incomplete for some footprints.
- Facade orientation is estimated from geometry, not surveyed.

---

## Status

| Step | Status |
|---|---|
| Topic & study area defined | Done |
| Data sources identified | Done |
| Spatial unit of analysis planned | Done |
| Data collection | Pending |
| Feature engineering | Pending |
| Modeling | Pending |
| Interactive map | Pending |
