import streamlit as st
import folium
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_folium import st_folium

from models import (
    calculate_coverage_grid, calculate_multi_antenna_grid,
    frequency_band, select_model, rain_attenuation_db, calculate_rssi
)

# ──────────────────────────────────────────
# Page configuration
# ──────────────────────────────────────────
st.set_page_config(
    page_title="Radio Coverage Simulator",
    page_icon="📡",
    layout="wide"
)

st.title("📡 Radio Coverage Simulator")
st.caption("Okumura-Hata / COST-231 / FSPL · ITU-R P.838 rain attenuation · Multi-antenna best-server")

# ──────────────────────────────────────────
# Session state
# ──────────────────────────────────────────
if "data"     not in st.session_state: st.session_state.data     = None
if "params"   not in st.session_state: st.session_state.params   = {}
if "antennas" not in st.session_state: st.session_state.antennas = []

# ──────────────────────────────────────────
# Legend
# ──────────────────────────────────────────
LEGEND = [
    ("green",  "Excellent  (> −80 dBm)"),
    ("blue",   "Good       (−80 to −90 dBm)"),
    ("orange", "Marginal   (−90 to −100 dBm)"),
    ("red",    "No coverage  (< −100 dBm)"),
]

# ──────────────────────────────────────────
# Frequency band presets
# ──────────────────────────────────────────
FREQ_PRESETS = {
    "900 MHz — GSM / LTE (mobile)":       900,
    "1800 MHz — LTE Band 3 (mobile)":     1800,
    "2100 MHz — UMTS / LTE (mobile)":     2100,
    "7 GHz — Microwave backhaul":         7000,
    "15 GHz — Microwave backhaul":        15000,
    "23 GHz — Microwave backhaul":        23000,
    "38 GHz — Microwave backhaul":        38000,
}

# ──────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────
with st.sidebar:
    st.header("Simulation mode")
    mode = st.radio("", ["Single antenna", "Multiple antennas"], horizontal=True)

    st.divider()

    # ── Frequency ──
    st.subheader("Frequency")
    use_preset = st.toggle("Use frequency preset", value=True)

    if use_preset:
        preset_label = st.selectbox("Band", list(FREQ_PRESETS.keys()))
        f_mhz = FREQ_PRESETS[preset_label]
        st.caption(f"→ {f_mhz} MHz")
    else:
        f_mhz = st.slider("Frequency (MHz)", 150, 40000, 900, step=50)

    band = frequency_band(f_mhz)

    # Band info badge
    if band == "mobile":
        st.info("📱 Mobile band — Okumura-Hata model")
    elif band == "mobile_high":
        st.info("📱 Mobile high-band — COST-231 Hata model")
    else:
        st.warning("📡 Microwave band — Free Space Path Loss (ITU-R P.530)")

    st.divider()

    # ── RF parameters ──
    st.subheader("RF parameters")
    h_mobile    = st.slider("Mobile terminal height (m)",  1,  10,  2)
    g_rx_dbi    = st.slider("Rx antenna gain (dBi)",       0,  40,  0,
                            help="Mobile networks: ~0 dBi · Microwave dishes: 30–40 dBi")
    if band == "microwave":
        environment = "urban"   # not used in FSPL, fixed silently
    else:
        environment = st.selectbox("Environment", ["urban", "suburban", "rural"])

    st.divider()

    # ── Rain attenuation ──
    st.subheader("🌧️ Rain attenuation (ITU-R P.838)")
    rain_enabled = st.toggle("Enable rain attenuation")
    rain_rate    = 0.0

    if rain_enabled:
        if f_mhz < 5000:
            st.warning("⚠️ Below 5 GHz rain attenuation is negligible. "
                       "Switch to a microwave band (≥ 7 GHz) to see a real effect.")
        else:
            rain_rate = st.select_slider(
                "Rain intensity",
                options=[0, 5, 10, 25, 50, 100],
                value=25,
                format_func=lambda x: {
                    0:   "0 mm/h — Dry",
                    5:   "5 mm/h — Drizzle",
                    10:  "10 mm/h — Light rain",
                    25:  "25 mm/h — Moderate rain",
                    50:  "50 mm/h — Heavy rain",
                    100: "100 mm/h — Extreme rain",
                }[x]
            )

    st.divider()

    # ── Single antenna ──
    if mode == "Single antenna":
        st.subheader("Antenna parameters")
        lat       = st.number_input("Latitude",         value=41.3874, format="%.4f")
        lon       = st.number_input("Longitude",        value=2.1686,  format="%.4f")
        h_base    = st.slider("Antenna height (m)",      10, 150, 30)
        p_tx_dbm  = st.slider("Tx power (dBm)",          20,  46, 43)
        g_tx_dbi  = st.slider("Tx antenna gain (dBi)",    0,  40, 15,
                              help="Mobile: 15–18 dBi · Microwave dish: 30–40 dBi")
        radius_km = st.slider("Simulation radius (km)",   1,  50,  8)

        calculate = st.button("Calculate coverage", width="stretch")

        if calculate:
            with st.spinner("Calculating..."):
                data = calculate_coverage_grid(
                    antenna_lat     = lat,
                    antenna_lon     = lon,
                    f_mhz           = f_mhz,
                    p_tx_dbm        = p_tx_dbm,
                    h_base          = h_base,
                    h_mobile        = h_mobile,
                    g_tx_dbi        = g_tx_dbi,
                    g_rx_dbi        = g_rx_dbi,
                    environment     = environment,
                    radius_km       = radius_km,
                    rain_rate_mmh   = rain_rate,
                    steps           = 45,
                )
                st.session_state.data   = data
                st.session_state.params = {
                    "mode": "single",
                    "lat": lat, "lon": lon,
                    "f_mhz": f_mhz, "band": band,
                    "h_base": h_base, "p_tx_dbm": p_tx_dbm,
                    "g_tx_dbi": g_tx_dbi, "environment": environment,
                    "radius_km": radius_km, "rain_rate": rain_rate,
                }

    # ── Multiple antennas ──
    else:
        st.subheader("Antenna list")

        with st.expander("➕ Add antenna"):
            a_name   = st.text_input("Name", value=f"BS-{len(st.session_state.antennas)+1}")
            a_lat    = st.number_input("Latitude",  value=41.3874, format="%.4f", key="a_lat")
            a_lon    = st.number_input("Longitude", value=2.1686,  format="%.4f", key="a_lon")
            a_h_base = st.slider("Height (m)",     10, 150, 30, key="a_h")
            a_p_tx   = st.slider("Tx power (dBm)", 20,  46, 43, key="a_p")
            a_g_tx   = st.slider("Gain (dBi)",      0,  40, 15, key="a_g")

            if st.button("Add antenna"):
                st.session_state.antennas.append({
                    "name":     a_name,
                    "lat":      a_lat,
                    "lon":      a_lon,
                    "h_base":   a_h_base,
                    "p_tx_dbm": a_p_tx,
                    "g_tx_dbi": a_g_tx,
                })
                st.rerun()

        if st.session_state.antennas:
            for i, ant in enumerate(st.session_state.antennas):
                col_a, col_b = st.columns([4, 1])
                col_a.markdown(f"**{ant['name']}** · {ant['lat']:.4f}, {ant['lon']:.4f}")
                if col_b.button("✕", key=f"del_{i}"):
                    st.session_state.antennas.pop(i)
                    st.rerun()
        else:
            st.caption("No antennas added yet.")

        calculate = st.button(
            "Calculate coverage", width="stretch",
            disabled=len(st.session_state.antennas) < 2
        )
        if len(st.session_state.antennas) < 2:
            st.caption("Add at least 2 antennas to calculate.")

        if calculate:
            with st.spinner("Calculating multi-antenna coverage..."):
                data = calculate_multi_antenna_grid(
                    antennas        = st.session_state.antennas,
                    f_mhz           = f_mhz,
                    h_mobile        = h_mobile,
                    g_rx_dbi        = g_rx_dbi,
                    environment     = environment,
                    rain_rate_mmh   = rain_rate,
                    steps           = 45,
                )
                st.session_state.data   = data
                st.session_state.params = {
                    "mode":        "multi",
                    "antennas":    list(st.session_state.antennas),
                    "f_mhz":       f_mhz,
                    "band":        band,
                    "environment": environment,
                    "rain_rate":   rain_rate,
                }

# ──────────────────────────────────────────
# Display
# ──────────────────────────────────────────
if st.session_state.data is not None:
    df = pd.DataFrame(st.session_state.data)
    p  = st.session_state.params

    # ── Metrics ──
    total = len(df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calculated points", total)
    c2.metric("Excellent coverage",
              f"{len(df[df.rssi_dbm > -80]) / total * 100:.0f} %")
    c3.metric("Useful coverage (> −100 dBm)",
              f"{len(df[df.rssi_dbm > -100]) / total * 100:.0f} %")
    c4.metric("Average RSSI", f"{df.rssi_dbm.mean():.1f} dBm")

    if p.get("rain_rate", 0) > 0:
        st.warning(
            f"🌧️ Rain attenuation active — {p['rain_rate']} mm/h (ITU-R P.838). "
            f"Coverage is reduced compared to dry conditions."
        )

    st.divider()

    col_map, col_info = st.columns([3, 1])

    with col_map:
        center_lat = df["lat"].mean()
        center_lon = df["lon"].mean()
        m = folium.Map(location=[center_lat, center_lon],
                       zoom_start=12, tiles="CartoDB positron")

        for row in df.itertuples():
            folium.CircleMarker(
                location     = [row.lat, row.lon],
                radius       = 4,
                color        = row.color,
                fill         = True,
                fill_opacity = 0.65,
                weight       = 0,
                tooltip      = (
                    f"{row.rssi_dbm} dBm"
                    + (f" · {row.serving_antenna}" if hasattr(row, "serving_antenna") else "")
                )
            ).add_to(m)

        if p["mode"] == "single":
            folium.Marker(
                location = [p["lat"], p["lon"]],
                tooltip  = "Base station",
                icon     = folium.Icon(color="black", icon="signal", prefix="fa")
            ).add_to(m)
        else:
            antenna_colors = ["red", "purple", "darkblue", "darkgreen",
                              "cadetblue", "darkred", "orange", "pink"]
            for i, ant in enumerate(p["antennas"]):
                folium.Marker(
                    location = [ant["lat"], ant["lon"]],
                    tooltip  = f"{ant['name']} — {ant['p_tx_dbm']} dBm · {ant['h_base']} m",
                    icon     = folium.Icon(
                        color=antenna_colors[i % len(antenna_colors)],
                        icon="signal", prefix="fa"
                    )
                ).add_to(m)

        st_folium(m, width=700, height=500)

    with col_info:
        st.subheader("Legend")
        for color, label in LEGEND:
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:10px'>"
                f"<div style='width:14px;height:14px;border-radius:50%;"
                f"background:{color};flex-shrink:0'></div>"
                f"<span style='font-size:13px'>{label}</span></div>",
                unsafe_allow_html=True
            )

        st.divider()
        st.subheader("Parameters")

        band_labels = {
            "mobile":      "Okumura-Hata",
            "mobile_high": "COST-231 Hata",
            "microwave":   "FSPL (ITU-R P.530)",
        }
        st.markdown(f"**Frequency:** {p['f_mhz']} MHz")
        st.markdown(f"**Model:** {band_labels.get(p['band'], '—')}")
        st.markdown(f"**Environment:** {p.get('environment', '—')}")
        rain = p.get("rain_rate", 0)
        st.markdown(f"**Rain:** {'off' if rain == 0 else f'{rain} mm/h'}")

        if p["mode"] == "single":
            st.markdown(f"**Antenna height:** {p['h_base']} m")
            st.markdown(f"**Tx power:** {p['p_tx_dbm']} dBm")
            st.markdown(f"**Tx gain:** {p['g_tx_dbi']} dBi")
            st.markdown(f"**Radius:** {p['radius_km']} km")
        else:
            st.divider()
            st.subheader("Antennas")
            for ant in p["antennas"]:
                st.markdown(
                    f"**{ant['name']}** · {ant['p_tx_dbm']} dBm "
                    f"· {ant['h_base']} m · {ant['g_tx_dbi']} dBi"
                )

    st.divider()

    with st.expander("View results table"):
        cols = ["lat", "lon", "rssi_dbm", "coverage_level"]
        if "distance_km"     in df.columns: cols.insert(2, "distance_km")
        if "path_loss_db"    in df.columns: cols.insert(3, "path_loss_db")
        if "rain_loss_db"    in df.columns: cols.insert(4, "rain_loss_db")
        if "serving_antenna" in df.columns: cols.append("serving_antenna")

        rename = {
            "distance_km":     "Distance (km)",
            "path_loss_db":    "Path Loss (dB)",
            "rain_loss_db":    "Rain Loss (dB)",
            "rssi_dbm":        "RSSI (dBm)",
            "coverage_level":  "Level",
            "serving_antenna": "Serving antenna",
        }
        st.dataframe(
            df[cols].rename(columns=rename).sort_values("RSSI (dBm)", ascending=False),
            use_container_width=True
        )

        st.download_button(
            label="⬇️ Download CSV",
            data=df[cols].rename(columns=rename).to_csv(index=False),
            file_name="coverage_results.csv",
            mime="text/csv",
        )

    st.divider()

    # ── RSSI vs Distance chart ──
    st.subheader("📈 RSSI vs Distance")
    st.caption("Signal level as a function of distance for different environments and rain conditions.")

    distances = np.linspace(0.1, p.get("radius_km", 20), 200)
    chart_f    = p["f_mhz"]
    chart_band = p["band"]

    # Reference antenna parameters for the chart
    if p["mode"] == "single":
        chart_p_tx   = p["p_tx_dbm"]
        chart_g_tx   = p["g_tx_dbi"]
        chart_h_base = p["h_base"]
    else:
        # Use average of all antennas
        chart_p_tx   = np.mean([a["p_tx_dbm"] for a in p["antennas"]])
        chart_g_tx   = np.mean([a["g_tx_dbi"] for a in p["antennas"]])
        chart_h_base = np.mean([a["h_base"]   for a in p["antennas"]])

    model = select_model(chart_f)

    fig = go.Figure()

    # Environments to plot (only for mobile bands)
    if chart_band in ("mobile", "mobile_high"):
        envs = [
            ("urban",    "#e63946", "Urban"),
            ("suburban", "#f4a261", "Suburban"),
            ("rural",    "#2a9d8f", "Rural"),
        ]
    else:
        envs = [("urban", "#e63946", "Line-of-sight (FSPL)")]

    for env, color, label in envs:
        rssi_vals = [
            calculate_rssi(
                chart_p_tx, chart_g_tx,
                model(chart_f, d, chart_h_base, 1.5, env),
                0.0
            )
            for d in distances
        ]
        fig.add_trace(go.Scatter(
            x=distances, y=rssi_vals,
            mode="lines", name=label,
            line=dict(color=color, width=2.5)
        ))

    # Rain curve (only if rain was active and f >= 5 GHz)
    rain = p.get("rain_rate", 0)
    if rain > 0 and chart_f >= 5000:
        env_rain = "urban" if chart_band in ("mobile", "mobile_high") else "urban"
        rssi_rain = [
            calculate_rssi(
                chart_p_tx, chart_g_tx,
                model(chart_f, d, chart_h_base, 1.5, env_rain),
                rain_attenuation_db(chart_f, d, rain)
            )
            for d in distances
        ]
        fig.add_trace(go.Scatter(
            x=distances, y=rssi_rain,
            mode="lines", name=f"Urban + rain ({rain} mm/h)",
            line=dict(color="#9b5de5", width=2.5, dash="dash")
        ))

    # Coverage threshold lines
    thresholds = [
        (-80,  "Excellent threshold",  "green",  "dot"),
        (-90,  "Good threshold",       "blue",   "dot"),
        (-100, "Marginal threshold",   "orange", "dot"),
    ]
    for val, label, color, dash in thresholds:
        fig.add_hline(
            y=val, line_dash=dash, line_color=color,
            line_width=1.2, opacity=0.7,
            annotation_text=label,
            annotation_position="bottom right",
            annotation_font_size=11,
        )

    fig.update_layout(
        xaxis_title="Distance (km)",
        yaxis_title="RSSI (dBm)",
        yaxis=dict(range=[-130, -40]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=40, b=10),
        height=400,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=12),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Configure the parameters in the left panel and press **Calculate coverage**.")
    m = folium.Map(location=[41.3874, 2.1686], zoom_start=11, tiles="CartoDB positron")
    st_folium(m, width=700, height=450)