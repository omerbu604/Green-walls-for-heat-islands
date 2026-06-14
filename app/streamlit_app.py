"""
Urban Heat Island - Green Wall Recommender
Tel Aviv | GeoAI Course Project
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium
from pathlib import Path
import branca.colormap as cm
import matplotlib.pyplot as plt

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
LAYERS = ROOT / "Layers"
OUTPUTS = ROOT / "outputs"

st.set_page_config(
    page_title="Tel Aviv — Green Wall Recommender",
    page_icon="🌿",
    layout="wide",
)

# ── Load raw data (cached, never mutated) ───────────────────────────────────
@st.cache_data
def load_data():
    bld = gpd.read_file(OUTPUTS / "tel_aviv_buildings_scored.gpkg").to_crs(4326)
    grd = gpd.read_file(OUTPUTS / "tel_aviv_grid_features.gpkg").to_crs(4326)
    bdr = gpd.read_file(LAYERS / "tel_aviv_border.geojson")
    return bld, grd, bdr

_buildings_raw, grid, border = load_data()

# ── Recompute score with fixed parameters ───────────────────────────────────
# Original DECAY_DISTANCE=50m was too tight — most buildings collapsed to ~0
# and min-max normalization mapped everything to score=1.
# 300m is a realistic urban cooling influence radius.
DECAY_DISTANCE = 300

@st.cache_data
def compute_scores():
    bld = _buildings_raw.copy()
    decay = np.exp(-bld["dist_to_hotspot"] / DECAY_DISTANCE)
    raw = (
        bld["heat_priority"]
        * bld["eligible_wall_area"]
        * bld["sun_score"]
        * decay
        * (bld["predicted_cooling"] + 0.01)
    )
    # Log-transform before normalising to prevent outlier compression
    raw_log = np.log1p(raw)
    bld["green_wall_score"] = (
        1 + 9 * (raw_log - raw_log.min()) / (raw_log.max() - raw_log.min())
    )
    bld["score_per_cost"] = bld["green_wall_score"] / bld["cost_ils"].clip(lower=1)
    # Predicted cooling in °C (from XGBoost scenario simulation)
    bld["cooling_C"] = bld["predicted_cooling"].round(3)
    return bld

buildings = compute_scores()

# ── Sidebar controls ─────────────────────────────────────────────────────────
st.sidebar.title("🌿 Green Wall Recommender")
st.sidebar.markdown("**Urban Heat Island — Tel Aviv**")
st.sidebar.markdown("---")

budget_m = st.sidebar.slider(
    "Budget (million ₪)",
    min_value=1, max_value=100, value=20, step=1,
    help="Total budget for green wall installation"
)
budget = budget_m * 1_000_000

st.sidebar.markdown("---")
show_hotspots = st.sidebar.checkbox("Show heat hotspots", value=True)
show_all_bld  = st.sidebar.checkbox("Show all buildings", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Color buildings by:**")
layer_choice = st.sidebar.radio(
    "Color buildings by:",
    ["Green Wall Score", "Predicted Cooling (°C)", "Sun Score", "Heat Priority", "Building Height"],
    label_visibility="collapsed"
)

# ── Budget optimizer ─────────────────────────────────────────────────────────
@st.cache_data
def run_optimizer(budget_ils):
    bld = compute_scores()
    ranked = bld.sort_values("score_per_cost", ascending=False)
    selected, spent = [], 0.0
    for _, row in ranked.iterrows():
        if spent + row["cost_ils"] <= budget_ils:
            selected.append(row["id"])
            spent += row["cost_ils"]
    return set(selected), spent

selected_ids, total_spent = run_optimizer(budget)
buildings["selected"] = buildings["id"].isin(selected_ids)
n_selected = len(selected_ids)

sel_bld = buildings[buildings["selected"]]
avg_score   = sel_bld["green_wall_score"].mean()
total_cool  = sel_bld["predicted_cooling"].sum()
avg_cool    = sel_bld["predicted_cooling"].mean()

# ── Header metrics ───────────────────────────────────────────────────────────
st.title("Tel Aviv — Urban Heat Island & Green Wall Recommender")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Budget", f"₪{budget_m}M")
c2.metric("Selected buildings", f"{n_selected:,}")
c3.metric("Budget used", f"₪{total_spent/1e6:.1f}M ({total_spent/budget*100:.0f}%)")
c4.metric("Avg green wall score", f"{avg_score:.1f} / 10")
c5.metric("Avg predicted cooling", f"{avg_cool:.2f} °C", help="XGBoost model: LST reduction per selected building")

st.markdown("---")

# ── Colour scales ────────────────────────────────────────────────────────────
col_map = {
    "Green Wall Score":        ("green_wall_score", ["#d73027","#fee08b","#1a9850"], 1,   10),
    "Predicted Cooling (°C)":  ("cooling_C",        ["#f7fbff","#6baed6","#08306b"], 0,   buildings["cooling_C"].quantile(0.95)),
    "Sun Score":               ("sun_score",        ["#ffffb2","#fd8d3c","#bd0026"], 0,   1),
    "Heat Priority":           ("heat_priority",    ["#4575b4","#ffffbf","#d73027"], 0,   1),
    "Building Height":         ("height",           ["#ffffcc","#fd8d3c","#800026"], 0, 100),
}
col_field, cmap_colors, vmin, vmax = col_map[layer_choice]

colormap = cm.LinearColormap(
    colors=cmap_colors,
    vmin=vmin, vmax=vmax,
    caption=layer_choice,
)

def building_style(feature):
    val = feature["properties"].get(col_field) or 0
    return {
        "fillColor": colormap(min(max(val, vmin), vmax)),
        "color": "none",
        "weight": 0,
        "fillOpacity": 0.8,
    }

# ── Build Folium map ─────────────────────────────────────────────────────────
center = [32.08, 34.78]
m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")
colormap.add_to(m)

# City border
folium.GeoJson(
    border.__geo_interface__,
    style_function=lambda _: {"color": "#2c3e50", "weight": 2, "fillOpacity": 0},
    name="City border",
).add_to(m)

# Heat hotspots
if show_hotspots:
    hotspots = grid[grid["is_hotspot"] == 1]
    folium.GeoJson(
        hotspots.__geo_interface__,
        style_function=lambda _: {"fillColor":"#e74c3c","color":"none","fillOpacity":0.3,"weight":0},
        name="Heat hotspots",
        tooltip=folium.GeoJsonTooltip(
            ["mean_LST", "heat_priority", "predicted_cooling"],
            aliases=["LST (°C)", "Heat priority", "Predicted cooling (°C)"],
        ),
    ).add_to(m)

# All buildings (background layer)
if show_all_bld:
    _cols = list(dict.fromkeys([
        "id", "height", col_field, "green_wall_score", "cooling_C",
        "sun_score", "heat_priority", "cost_ils", "geometry"
    ]))
    folium.GeoJson(
        buildings[_cols].copy().__geo_interface__,
        style_function=building_style,
        name=f"All buildings ({layer_choice})",
        tooltip=folium.GeoJsonTooltip(
            fields=["id", "height", "green_wall_score", "cooling_C", "sun_score", "cost_ils"],
            aliases=["ID", "Height (m)", "Score (1-10)", "Cooling (°C)", "Sun score", "Cost (₪)"],
            localize=True,
        ),
    ).add_to(m)

# Selected buildings (green overlay)
folium.GeoJson(
    sel_bld[["id","height","green_wall_score","cooling_C","sun_score","cost_ils","geometry"]].copy().__geo_interface__,
    style_function=lambda _: {"fillColor":"#27ae60","color":"#155d27","weight":1,"fillOpacity":0.9},
    name=f"Selected (₪{budget_m}M budget)",
    tooltip=folium.GeoJsonTooltip(
        fields=["id", "height", "green_wall_score", "cooling_C", "cost_ils"],
        aliases=["ID", "Height (m)", "Score (1-10)", "Predicted cooling (°C)", "Cost (₪)"],
        localize=True,
    ),
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# ── Map + info panel ─────────────────────────────────────────────────────────
col_map_col, col_info = st.columns([3, 1])

with col_map_col:
    st_folium(m, width=900, height=640, returned_objects=[])

with col_info:
    st.subheader("Top 10 selected")
    top10 = (sel_bld
             .nlargest(10, "green_wall_score")
             [["id","height","green_wall_score","cooling_C","cost_ils"]]
             .rename(columns={"id":"ID","height":"H(m)","green_wall_score":"Score",
                              "cooling_C":"Cool(°C)","cost_ils":"Cost(₪)"})
             .reset_index(drop=True))
    top10["Cost(₪)"] = top10["Cost(₪)"].apply(lambda x: f"₪{x:,.0f}")
    top10["Score"]   = top10["Score"].round(1)
    top10["Cool(°C)"]= top10["Cool(°C)"].round(3)
    st.dataframe(top10, use_container_width=True, height=300)

    st.markdown("---")
    st.subheader("Score distribution")
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ax.hist(buildings["green_wall_score"], bins=40, color="#27ae60", alpha=0.7, edgecolor="white", lw=0.3)
    ax.axvline(avg_score, color="#e74c3c", linestyle="--", lw=1.5, label=f"Avg selected: {avg_score:.1f}")
    ax.set_xlabel("Green wall score"); ax.set_ylabel("Buildings")
    ax.legend(fontsize=7); ax.tick_params(labelsize=7)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Predicted cooling")
    fig2, ax2 = plt.subplots(figsize=(4, 2.5))
    ax2.hist(sel_bld["predicted_cooling"], bins=25, color="#2980b9", alpha=0.8, edgecolor="white", lw=0.3)
    ax2.axvline(avg_cool, color="#e74c3c", linestyle="--", lw=1.5, label=f"Mean: {avg_cool:.3f}°C")
    ax2.set_xlabel("LST reduction (°C)"); ax2.set_ylabel("Buildings")
    ax2.legend(fontsize=7); ax2.tick_params(labelsize=7)
    ax2.set_title("XGBoost scenario simulation", fontsize=8)
    fig2.tight_layout()
    st.pyplot(fig2, use_container_width=True)

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Data: Sentinel-2 NDVI · Landsat LST (GEE) · OSM roads & water · Tel Aviv building registry.  "
    "Model: XGBoost LST regression (R²=0.41). Score: heat_priority × wall_area × sun_score × e^(−dist/300m) × cooling.  "
    "GeoAI Course Project — 2026"
)
