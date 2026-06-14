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

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
LAYERS = ROOT / "Layers"
OUTPUTS = ROOT / "outputs"

st.set_page_config(
    page_title="Tel Aviv — Green Wall Recommender",
    page_icon="🌿",
    layout="wide",
)

# ── Load data (cached) ───────────────────────────────────────────────────────
@st.cache_data
def load_data():
    buildings = gpd.read_file(OUTPUTS / "tel_aviv_buildings_scored.gpkg").to_crs(4326)
    grid = gpd.read_file(OUTPUTS / "tel_aviv_grid_features.gpkg").to_crs(4326)
    border = gpd.read_file(LAYERS / "tel_aviv_border.geojson")
    return buildings, grid, border

buildings, grid, border = load_data()

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
show_all_bld = st.sidebar.checkbox("Show all buildings", value=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Map layer**")
layer_choice = st.sidebar.radio(
    "Color buildings by:",
    ["Green Wall Score", "Sun Score", "Heat Priority", "Building Height"],
    label_visibility="collapsed"
)

# ── Budget optimizer ─────────────────────────────────────────────────────────
@st.cache_data
def run_optimizer(budget_ils):
    ranked = buildings.sort_values("score_per_cost", ascending=False)
    selected, spent = [], 0.0
    for _, row in ranked.iterrows():
        if spent + row["cost_ils"] <= budget_ils:
            selected.append(row["id"])
            spent += row["cost_ils"]
    return set(selected), spent

selected_ids, total_spent = run_optimizer(budget)
buildings["selected"] = buildings["id"].isin(selected_ids)
n_selected = len(selected_ids)

# ── Header metrics ───────────────────────────────────────────────────────────
st.title("Tel Aviv — Urban Heat Island & Green Wall Recommender")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Budget", f"₪{budget_m}M")
col2.metric("Selected buildings", f"{n_selected:,}")
col3.metric("Budget used", f"₪{total_spent/1e6:.1f}M  ({total_spent/budget*100:.0f}%)")
avg_score = buildings[buildings["selected"]]["green_wall_score"].mean()
col4.metric("Avg green wall score", f"{avg_score:.1f} / 10")

st.markdown("---")

# ── Build Folium map ─────────────────────────────────────────────────────────
center = [32.08, 34.78]
m = folium.Map(location=center, zoom_start=13, tiles="CartoDB positron")

# City border
border_json = border.__geo_interface__
folium.GeoJson(
    border_json,
    style_function=lambda _: {"color": "#2c3e50", "weight": 2, "fillOpacity": 0},
    name="City border",
).add_to(m)

# Heat hotspots layer
if show_hotspots:
    hotspots = grid[grid["is_hotspot"] == 1]
    folium.GeoJson(
        hotspots.__geo_interface__,
        style_function=lambda _: {
            "fillColor": "#e74c3c", "color": "none",
            "fillOpacity": 0.25, "weight": 0
        },
        name="Heat hotspots",
        tooltip=folium.GeoJsonTooltip(["mean_LST", "heat_priority"],
                                       aliases=["LST (°C)", "Heat priority"]),
    ).add_to(m)

# Colour scale for buildings
col_map = {
    "Green Wall Score": ("green_wall_score", "RdYlGn", 1, 10),
    "Sun Score":        ("sun_score",         "YlOrRd", 0, 1),
    "Heat Priority":    ("heat_priority",     "RdYlBu_r", 0, 1),
    "Building Height":  ("height",            "YlOrRd", 0, 100),
}
col_field, cmap_name, vmin, vmax = col_map[layer_choice]

colormap = cm.LinearColormap(
    colors=["#2ecc71", "#f1c40f", "#e74c3c"] if cmap_name == "RdYlGn" else
           ["#ffffb2", "#fecc5c", "#fd8d3c", "#e31a1c"],
    vmin=vmin, vmax=vmax,
    caption=layer_choice,
)
colormap.add_to(m)

def building_style(feature):
    val = feature["properties"].get(col_field, 0) or 0
    t = (val - vmin) / max(vmax - vmin, 1e-9)
    t = max(0, min(1, t))
    # interpolate colour
    colors_rgb = colormap.colors if hasattr(colormap, "colors") else []
    fill = colormap(val)
    return {
        "fillColor": fill,
        "color": "#555",
        "weight": 0.3,
        "fillOpacity": 0.75,
    }

# All buildings layer
if show_all_bld:
    bld_data = buildings[["id", "height", col_field, "green_wall_score",
                           "sun_score", "heat_priority", "cost_ils",
                           "eligible_wall_area", "geometry"]].copy()
    folium.GeoJson(
        bld_data.__geo_interface__,
        style_function=building_style,
        name=f"Buildings ({layer_choice})",
        tooltip=folium.GeoJsonTooltip(
            fields=["id", "height", "green_wall_score", "sun_score",
                    "heat_priority", "cost_ils"],
            aliases=["ID", "Height (m)", "GW Score (1-10)", "Sun Score",
                     "Heat Priority", "Cost (₪)"],
            localize=True,
        ),
    ).add_to(m)

# Selected buildings overlay (green)
selected_bld = buildings[buildings["selected"]]
folium.GeoJson(
    selected_bld.__geo_interface__,
    style_function=lambda _: {
        "fillColor": "#27ae60", "color": "#1a7a43",
        "weight": 1.5, "fillOpacity": 0.9,
    },
    name=f"Selected for ₪{budget_m}M budget",
    tooltip=folium.GeoJsonTooltip(
        fields=["id", "height", "green_wall_score", "sun_score", "cost_ils"],
        aliases=["ID", "Height (m)", "GW Score (1-10)", "Sun Score", "Est. Cost (₪)"],
        localize=True,
    ),
).add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

# ── Display map ──────────────────────────────────────────────────────────────
col_map_col, col_info = st.columns([3, 1])

with col_map_col:
    st_folium(m, width=900, height=620, returned_objects=[])

with col_info:
    st.subheader("Top 10 buildings")
    st.markdown(f"*Selected for ₪{budget_m}M budget*")
    top10 = (buildings[buildings["selected"]]
             .nlargest(10, "green_wall_score")
             [["id", "height", "green_wall_score", "cost_ils"]]
             .rename(columns={"id": "ID", "height": "H (m)",
                              "green_wall_score": "Score", "cost_ils": "Cost (₪)"})
             .reset_index(drop=True))
    top10["Cost (₪)"] = top10["Cost (₪)"].apply(lambda x: f"₪{x:,.0f}")
    top10["Score"] = top10["Score"].round(1)
    st.dataframe(top10, use_container_width=True, height=340)

    st.markdown("---")
    st.subheader("Score distribution")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ax.hist(buildings["green_wall_score"], bins=30, color="#27ae60", alpha=0.7,
            edgecolor="white", linewidth=0.3)
    ax.axvline(avg_score, color="#e74c3c", linestyle="--", linewidth=1.5,
               label=f"Selected avg: {avg_score:.1f}")
    ax.set_xlabel("Green wall score"); ax.set_ylabel("Buildings")
    ax.legend(fontsize=7); ax.tick_params(labelsize=7)
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Data: Sentinel-2 NDVI, Landsat LST (GEE), OSM roads & water, Tel Aviv building registry.  "
    "Model: XGBoost LST regression (R²=0.41). Scoring: heat priority × wall area × sun exposure × cooling impact.  "
    "GeoAI Course Project — 2026"
)
