"""TEJAS — Aditya-L1 Solar Flare Mission Control.

A dark "mission control" dashboard over the nowcasting pipeline outputs:
live SoLEXS soft X-ray light curve with a moving detection threshold, GOES flux
overlay, real-time flare alerts with GOES class, the validated flare catalogue,
and the calibration / validation science.

Run:  streamlit run app/dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO = Path(__file__).resolve().parent.parent
CAT_PATH = REPO / "outputs" / "catalogs" / "solexs_flares.csv"
VAL_PATH = REPO / "outputs" / "catalogs" / "validation.json"
LC_PATH = REPO / "outputs" / "processed" / "lightcurve.parquet"

# ----------------------------------------------------------------------
# Palette
# ----------------------------------------------------------------------
BG = "#0a0e17"
PANEL = "#121a2a"
CYAN = "#22d3ee"
AMBER = "#fbbf24"
MAGENTA = "#e879f9"
GRID = "rgba(148,163,184,0.12)"
TEXT = "#e5e7eb"
MUTED = "#94a3b8"

CLASS_COLOR = {"A": "#34d399", "B": "#34d399", "C": "#fbbf24",
               "M": "#fb923c", "X": "#ef4444", "—": "#64748b"}


def cls_color(c: str) -> str:
    return CLASS_COLOR.get(str(c)[:1], "#64748b")


st.set_page_config(page_title="TEJAS · Solar Flare Mission Control",
                   page_icon="☀️", layout="wide")

st.markdown(f"""
<style>
  .stApp {{ background:
      radial-gradient(1200px 600px at 80% -10%, #14203a 0%, {BG} 55%); }}
  #MainMenu, footer {{ visibility: hidden; }}
  .block-container {{ padding-top: 1.2rem; max-width: 1500px; }}
  .tejas-title {{ font-size: 2.0rem; font-weight: 800; letter-spacing: .14em;
      color: {TEXT}; margin: 0; }}
  .tejas-title span {{ color: {CYAN}; text-shadow: 0 0 18px {CYAN}66; }}
  .tejas-sub {{ color: {MUTED}; letter-spacing: .22em; font-size: .72rem;
      text-transform: uppercase; margin-top: .2rem; }}
  .kpi {{ background: linear-gradient(180deg, {PANEL} 0%, #0d1422 100%);
      border: 1px solid rgba(148,163,184,.16); border-radius: 14px;
      padding: .85rem 1rem; box-shadow: 0 8px 30px #00000040; }}
  .kpi .v {{ font-size: 1.7rem; font-weight: 800; }}
  .kpi .l {{ color: {MUTED}; font-size: .68rem; text-transform: uppercase;
      letter-spacing: .12em; }}
  .badge {{ display:inline-block; padding:.12rem .55rem; border-radius:999px;
      font-weight:800; font-size:.8rem; color:#0a0e17; }}
  .flarecard {{ background:{PANEL}; border:1px solid rgba(148,163,184,.16);
      border-left:4px solid #888; border-radius:12px; padding:.6rem .8rem;
      margin-bottom:.5rem; }}
  .flarecard .t {{ color:{MUTED}; font-size:.72rem; }}
  .dot {{ height:9px; width:9px; border-radius:50%; display:inline-block;
      margin-right:6px; box-shadow:0 0 10px; }}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    cat = pd.read_csv(CAT_PATH, parse_dates=["start_time", "peak_time", "end_time"])
    val = json.loads(VAL_PATH.read_text())
    lc = pd.read_parquet(LC_PATH)
    lc["time"] = pd.to_datetime(lc["time"])
    lc["day"] = lc["time"].dt.strftime("%Y-%m-%d")
    cat["day"] = cat["peak_time"].dt.strftime("%Y-%m-%d")
    return cat, val, lc


if not CAT_PATH.exists():
    st.error("No pipeline outputs found. Run:  python -m tejas.pipeline")
    st.stop()

cat, val, lc = load_data()


# ----------------------------------------------------------------------
# Header + KPIs
# ----------------------------------------------------------------------
hl, hr = st.columns([3, 2])
with hl:
    st.markdown('<p class="tejas-title">TE<span>JAS</span> · SOLAR FLARE '
                'MISSION CONTROL</p>', unsafe_allow_html=True)
    st.markdown('<p class="tejas-sub">Aditya-L1 · SoLEXS soft X-ray '
                '· nowcasting & validation</p>', unsafe_allow_html=True)
with hr:
    d0, d1 = val["date_range"][0][:10], val["date_range"][1][:10]
    st.markdown(f'<div style="text-align:right;color:{MUTED};font-size:.8rem">'
                f'COVERAGE<br><b style="color:{TEXT}">{d0} → {d1}</b> · '
                f'{val["n_days"]} days</div>', unsafe_allow_html=True)


def kpi(col, value, label, color=TEXT):
    col.markdown(f'<div class="kpi"><div class="v" style="color:{color}">{value}'
                 f'</div><div class="l">{label}</div></div>', unsafe_allow_html=True)


k = st.columns(5)
kpi(k[0], val["n_flares"], "Flares detected", CYAN)
kpi(k[1], val["class_counts"].get("X", 0), "X-class flares", "#ef4444")
kpi(k[2], f'{val["goes_letter_class_agreement"]*100:.0f}%', "GOES class agreement", AMBER)
xr = val["recovery"]["by_class"].get("X", [0, 0])
kpi(k[3], f'{xr[0]}/{xr[1]}', "X-class recovered", "#34d399")
kpi(k[4], f'{val["peak_calibration"]["r"]:.3f}', "Calibration r", MAGENTA)

st.write("")
tab_live, tab_cat, tab_sci = st.tabs(
    ["🛰  LIVE MONITOR", "📁  FLARE CATALOG", "🔬  VALIDATION & SCIENCE"])


# ======================================================================
# TAB 1 — LIVE MONITOR
# ======================================================================
def day_figure(day_lc: pd.DataFrame, day_flares: pd.DataFrame,
               cursor: pd.Timestamp | None = None) -> go.Figure:
    fig = go.Figure()
    # SoLEXS counts (left, log)
    fig.add_trace(go.Scatter(
        x=day_lc["time"], y=day_lc["counts"], name="SoLEXS counts",
        mode="lines", line=dict(color=CYAN, width=1.6),
        fill="tozeroy", fillcolor="rgba(34,211,238,0.08)", yaxis="y1"))
    # Moving detection background/threshold (left)
    fig.add_trace(go.Scatter(
        x=day_lc["time"], y=day_lc["background"], name="Sliding background",
        mode="lines", line=dict(color=AMBER, width=1.2, dash="dot"), yaxis="y1"))
    # GOES flux (right, log)
    if "xrsb" in day_lc and day_lc["xrsb"].notna().any():
        fig.add_trace(go.Scatter(
            x=day_lc["time"], y=day_lc["xrsb"], name="GOES 1-8Å flux",
            mode="lines", line=dict(color=MAGENTA, width=1.4), yaxis="y2",
            opacity=0.9))
    # Flare peak markers, colored by class
    if len(day_flares):
        fig.add_trace(go.Scatter(
            x=day_flares["peak_time"], y=day_flares["peak_counts"],
            name="Detected flares", mode="markers", yaxis="y1",
            marker=dict(size=12, color=[cls_color(c) for c in day_flares["class_solexs"]],
                        line=dict(color="white", width=1), symbol="diamond"),
            text=[f"{r.class_solexs}  (GOES {r.class_goes})"
                  for r in day_flares.itertuples()],
            hovertemplate="%{text}<br>%{x}<extra></extra>"))
    if cursor is not None:
        fig.add_vline(x=cursor, line=dict(color="white", width=2, dash="solid"),
                      opacity=0.7)
    fig.update_layout(
        height=460, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="monospace", size=12),
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        xaxis=dict(gridcolor=GRID, showgrid=True),
        yaxis=dict(title="SoLEXS counts/s", type="log", gridcolor=GRID,
                   color=CYAN),
        yaxis2=dict(title="GOES W/m²", type="log", overlaying="y", side="right",
                    color=MAGENTA, showgrid=False, range=[-8, -3]))
    return fig


with tab_live:
    days = sorted(lc["day"].unique())
    # Default to the most active day (most flares).
    busiest = cat["day"].value_counts().idxmax() if len(cat) else days[0]
    c1, c2 = st.columns([3, 2])
    day = c1.selectbox("Observation day", days,
                       index=days.index(busiest) if busiest in days else 0)
    day_lc = lc[lc["day"] == day]
    day_flares = cat[cat["day"] == day].sort_values("peak_time")

    # Replay scrubber
    tmin = day_lc["time"].min().to_pydatetime()
    tmax = day_lc["time"].max().to_pydatetime()
    cursor = c2.slider("Replay cursor (UTC)", min_value=tmin, max_value=tmax,
                       value=tmax, format="HH:mm")
    cursor = pd.Timestamp(cursor)

    # Status banner based on cursor position vs flares.
    active = day_flares[(day_flares["start_time"] <= cursor) &
                        (day_flares["end_time"] >= cursor)]
    upcoming = day_flares[day_flares["peak_time"] > cursor]
    if len(active):
        f = active.iloc[0]
        st.markdown(
            f'<div style="background:linear-gradient(90deg,{cls_color(f.class_solexs)}33,'
            f'transparent);border-left:5px solid {cls_color(f.class_solexs)};'
            f'padding:.6rem 1rem;border-radius:10px;font-weight:700">'
            f'🚨 NOWCAST · FLARE IN PROGRESS · <span class="badge" '
            f'style="background:{cls_color(f.class_solexs)}">{f.class_solexs}</span>'
            f' &nbsp; peak {f.peak_time:%H:%M:%S} UTC · GOES {f.class_goes} · '
            f'{f.peak_significance:.0f}σ</div>', unsafe_allow_html=True)
    else:
        nxt = (f" · next flare {upcoming.iloc[0].peak_time:%H:%M} UTC"
               if len(upcoming) else "")
        st.markdown(
            f'<div style="background:{PANEL};border-left:5px solid #34d399;'
            f'padding:.6rem 1rem;border-radius:10px;color:{MUTED}">'
            f'🟢 QUIET · no active flare at {cursor:%H:%M:%S} UTC{nxt}</div>',
            unsafe_allow_html=True)

    st.plotly_chart(day_figure(day_lc, day_flares, cursor),
                    use_container_width=True, config={"displayModeBar": False})

    st.markdown(f"**{len(day_flares)} flare(s) detected on {day}**")
    for f in day_flares.itertuples():
        col = cls_color(f.class_solexs)
        dur = f.duration_s / 60
        st.markdown(
            f'<div class="flarecard" style="border-left-color:{col}">'
            f'<span class="dot" style="background:{col};color:{col}"></span>'
            f'<b>{f.flare_id}</b> &nbsp;'
            f'<span class="badge" style="background:{col}">{f.class_solexs}</span>'
            f' &nbsp; <span class="t">peak {f.peak_time:%H:%M:%S} · '
            f'{dur:.1f} min · {f.peak_significance:.0f}σ · '
            f'GOES truth {f.class_goes}</span></div>', unsafe_allow_html=True)


# ======================================================================
# TAB 2 — CATALOG
# ======================================================================
with tab_cat:
    st.subheader("Automated SoLEXS flare catalogue")
    letters = ["A", "B", "C", "M", "X"]
    pick = st.multiselect("Filter by class", letters,
                          default=["C", "M", "X"])
    view = cat[cat["class_solexs"].str[0].isin(pick)].copy()

    cc = st.columns(4)
    kpi(cc[0], len(view), "flares shown", CYAN)
    kpi(cc[1], (view["class_solexs"].str[0] == "X").sum(), "X-class", "#ef4444")
    kpi(cc[2], (view["class_solexs"].str[0] == "M").sum(), "M-class", "#fb923c")
    kpi(cc[3], f'{view["duration_s"].median()/60:.1f}m', "median duration", AMBER)
    st.write("")

    show = view[["flare_id", "start_time", "peak_time", "end_time",
                 "duration_s", "peak_counts", "peak_significance",
                 "class_solexs", "class_goes"]].copy()
    show["duration_min"] = (show.pop("duration_s") / 60).round(1)
    st.dataframe(show, use_container_width=True, height=430, hide_index=True)
    st.download_button("⬇  Download catalogue (CSV)",
                       cat.to_csv(index=False).encode(),
                       "tejas_solexs_flares.csv", "text/csv")

    # Class distribution
    dist = cat["class_solexs"].str[0].value_counts().reindex(letters).fillna(0)
    bar = go.Figure(go.Bar(x=letters, y=dist.values,
                           marker_color=[CLASS_COLOR[c] for c in letters]))
    bar.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT),
                      margin=dict(l=10, r=10, t=30, b=10),
                      title="Flares by GOES class",
                      yaxis=dict(gridcolor=GRID), xaxis=dict(gridcolor=GRID))
    st.plotly_chart(bar, use_container_width=True, config={"displayModeBar": False})


# ======================================================================
# TAB 3 — VALIDATION & SCIENCE
# ======================================================================
with tab_sci:
    st.subheader("How good is it? — validated against GOES ground truth")

    cL, cR = st.columns(2)
    # Calibration scatter
    valid = cat.dropna(subset=["flux_goes"])
    sc = go.Figure()
    sc.add_trace(go.Scatter(
        x=valid["peak_counts"], y=valid["flux_goes"], mode="markers",
        marker=dict(size=7, color=[cls_color(c) for c in valid["class_goes"]],
                    line=dict(color="#0a0e17", width=.5), opacity=.85),
        name="flares"))
    pc = val["peak_calibration"]
    xs = np.logspace(np.log10(valid["peak_counts"].min()),
                     np.log10(valid["peak_counts"].max()), 50)
    ys = 10 ** (pc["intercept"] + pc["slope"] * np.log10(xs))
    sc.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                            line=dict(color=CYAN, width=2, dash="dash"),
                            name=f'fit  r={pc["r"]:.3f}'))
    sc.update_layout(height=380, paper_bgcolor="rgba(0,0,0,0)",
                     plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT),
                     margin=dict(l=10, r=10, t=40, b=10),
                     title="SoLEXS counts → GOES flux calibration",
                     legend=dict(orientation="h", y=1.15),
                     xaxis=dict(title="SoLEXS peak counts", type="log",
                                gridcolor=GRID),
                     yaxis=dict(title="GOES peak flux (W/m²)", type="log",
                                gridcolor=GRID))
    cL.plotly_chart(sc, use_container_width=True, config={"displayModeBar": False})

    # Recovery by class
    rec = val["recovery"]["by_class"]
    classes = [c for c in ["C", "M", "X"] if c in rec]
    recovered = [rec[c][0] for c in classes]
    missed = [rec[c][1] - rec[c][0] for c in classes]
    rb = go.Figure()
    rb.add_trace(go.Bar(x=classes, y=recovered, name="recovered",
                        marker_color="#34d399"))
    rb.add_trace(go.Bar(x=classes, y=missed, name="missed",
                        marker_color="rgba(148,163,184,.35)"))
    rb.update_layout(barmode="stack", height=380,
                     paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                     font=dict(color=TEXT), margin=dict(l=10, r=10, t=40, b=10),
                     title=f'Recovery of catalogued flares '
                           f'({val["recovery"]["recall_overall"]*100:.0f}% overall)',
                     legend=dict(orientation="h", y=1.15),
                     xaxis=dict(gridcolor=GRID), yaxis=dict(gridcolor=GRID))
    cR.plotly_chart(rb, use_container_width=True, config={"displayModeBar": False})

    m1, m2, m3 = st.columns(3)
    kpi(m1, f'{val["goes_letter_class_agreement"]*100:.0f}%',
        "SoLEXS↔GOES class agreement", AMBER)
    kpi(m2, f'{val["minute_correlation_r"]:.2f}',
        "minute-level correlation r", MAGENTA)
    kpi(m3, f'{val["recovery"]["by_class"].get("X",[0,0])[0]}/'
        f'{val["recovery"]["by_class"].get("X",[0,0])[1]}',
        "X-class flares recovered", "#34d399")

    st.info("**Data-quality note:** the 2024-10-02 SoLEXS L1 file shares ~21 % of "
            "its high-count samples with 2024-10-01 (including an identical 23 655-"
            "count peak) while GOES shows no X-flare that day — a processing "
            "artifact. TEJAS detects this cross-day duplication and excludes the day.")
