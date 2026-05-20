"""
NYC Yellow Taxi Analytics Dashboard
====================================
Renders four Plotly visualizations from the gold-layer marts. Each chart
queries exactly one mart. Data source resolves automatically:
  - locally: the full dbt warehouse `dev.duckdb` (read-only), if present;
  - on Streamlit Cloud / a fresh clone: the committed parquet snapshots of
    the four marts in app/data/, so no dbt build is needed at runtime.

Visual identity follows the MetaCTO brand: deep teal-navy background
(#0F2028), vibrant orange accent (#F18700), Barlow headings + Inter body.
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from pathlib import Path

# ---------------------------------------------------------------------------
# Brand tokens (MetaCTO)
# ---------------------------------------------------------------------------
BRAND = {
    "bg": "#0F2028",
    "surface": "#16323D",
    "surface_alt": "#1B3C49",
    "border": "#274350",
    "orange": "#F18700",
    "orange_soft": "#F5A23D",
    "teal": "#2DD4BF",
    "text": "#E8EEF1",
    "text_muted": "#9DB2BD",
    "white": "#FFFFFF",
}

# Qualitative palette for categorical charts — accessible on the dark bg,
# orange-led to anchor to the brand.
CATEGORICAL = ["#F18700", "#2DD4BF", "#5B9BD5", "#A78BFA", "#FBBF24", "#FB7185", "#94A3B8"]

# Sequential scale for the heatmap: dark teal → brand orange.
HEATMAP_SCALE = [
    [0.0, "#0F2028"],
    [0.25, "#1E4D54"],
    [0.5, "#3F7A6E"],
    [0.7, "#C2820F"],
    [1.0, "#F18700"],
]

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

CASH_TIP_CAVEAT = (
    "Tips are observed only when captured digitally — credit-card (payment_type 1) "
    "and app-hailed Flex Fare (payment_type 0), including genuine $0.00 tips. Cash "
    "is never metered (it shows as $0.00 but is unobserved, not zero), so cash and "
    "non-standard settlements are excluded from tip-rate analysis."
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NYC Yellow Taxi Analytics · MetaCTO",
    page_icon="🚕",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "dev.duckdb"
DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------------
# Shared Plotly template
# ---------------------------------------------------------------------------
def _register_template():
    tpl = go.layout.Template()
    tpl.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=BRAND["text"], size=13),
        title=dict(font=dict(family="Barlow, sans-serif", color=BRAND["white"], size=18)),
        colorway=CATEGORICAL,
        xaxis=dict(gridcolor=BRAND["border"], zerolinecolor=BRAND["border"], linecolor=BRAND["border"]),
        yaxis=dict(gridcolor=BRAND["border"], zerolinecolor=BRAND["border"], linecolor=BRAND["border"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BRAND["border"]),
        margin=dict(l=20, r=20, t=56, b=20),
        hoverlabel=dict(bgcolor=BRAND["surface_alt"], bordercolor=BRAND["orange"],
                        font=dict(family="Inter, sans-serif", color=BRAND["text"])),
    )
    pio.templates["metacto"] = tpl


_register_template()
PLOTLY_TPL = "metacto"


# ---------------------------------------------------------------------------
# Global CSS — fonts, pill nav, header, metric cards
# ---------------------------------------------------------------------------
def inject_css():
    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Barlow:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            html, body, [class*="css"], .stMarkdown, p, span, div {{
                font-family: 'Inter', sans-serif;
            }}
            h1, h2, h3, h4 {{
                font-family: 'Barlow', sans-serif !important;
                letter-spacing: -0.01em;
                color: {BRAND['white']};
            }}
            .stApp {{
                background:
                    radial-gradient(1200px 600px at 85% -10%, rgba(241,135,0,0.10), transparent 60%),
                    radial-gradient(900px 500px at 0% 0%, rgba(45,212,191,0.06), transparent 55%),
                    {BRAND['bg']};
            }}
            .block-container {{ padding-top: 2rem; max-width: 1400px; }}

            /* Branded header bar */
            .mc-header {{
                display: flex; align-items: center; gap: 14px;
                padding: 4px 0 2px 0;
            }}
            .mc-logo-dot {{
                width: 12px; height: 12px; border-radius: 50%;
                background: {BRAND['orange']};
                box-shadow: 0 0 0 4px rgba(241,135,0,0.18);
            }}
            .mc-badge {{
                display:inline-block; font-family:'Inter',sans-serif; font-weight:600;
                font-size:0.72rem; letter-spacing:0.08em; text-transform:uppercase;
                color:{BRAND['orange_soft']}; background:rgba(241,135,0,0.10);
                border:1px solid rgba(241,135,0,0.30); padding:5px 12px; border-radius:999px;
            }}
            .mc-sub {{ color:{BRAND['text_muted']}; font-size:0.98rem; margin-top:6px; }}

            /* Tabs as pills */
            .stTabs [data-baseweb="tab-list"] {{
                gap: 8px; border-bottom: none; margin-top: 8px;
            }}
            .stTabs [data-baseweb="tab"] {{
                background: {BRAND['surface']};
                border: 1px solid {BRAND['border']};
                border-radius: 999px; padding: 8px 18px; color: {BRAND['text_muted']};
                font-weight: 600;
            }}
            .stTabs [aria-selected="true"] {{
                background: {BRAND['orange']} !important;
                color: {BRAND['white']} !important;
                border-color: {BRAND['orange']} !important;
            }}
            .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display:none; }}

            /* KPI metric cards */
            .mc-kpi {{
                background: linear-gradient(180deg, {BRAND['surface_alt']}, {BRAND['surface']});
                border: 1px solid {BRAND['border']};
                border-radius: 16px; padding: 18px 20px; height: 100%;
            }}
            .mc-kpi .label {{
                color: {BRAND['text_muted']}; font-size: 0.8rem; font-weight: 600;
                text-transform: uppercase; letter-spacing: 0.06em;
            }}
            .mc-kpi .value {{
                font-family:'Barlow',sans-serif; font-weight:700; font-size:1.9rem;
                color: {BRAND['white']}; margin-top: 6px;
                font-variant-numeric: tabular-nums;
            }}
            .mc-kpi .accent {{ color: {BRAND['orange']}; }}

            /* Caveat note */
            .mc-caveat {{
                background: rgba(241,135,0,0.07); border-left: 3px solid {BRAND['orange']};
                border-radius: 8px; padding: 10px 14px; color: {BRAND['text_muted']};
                font-size: 0.85rem; margin: 4px 0 14px 0;
            }}

            /* Section label */
            .mc-section {{
                font-family:'Barlow',sans-serif; font-weight:700; font-size:1.35rem;
                color:{BRAND['white']}; margin: 6px 0 2px 0;
            }}

            footer, #MainMenu {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(col, label, value, accent=False):
    cls = "value accent" if accent else "value"
    col.markdown(
        f'<div class="mc-kpi"><div class="label">{label}</div>'
        f'<div class="{cls}">{value}</div></div>',
        unsafe_allow_html=True,
    )


def caveat(text=CASH_TIP_CAVEAT):
    st.markdown(f'<div class="mc-caveat">{text}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data layer — resolve the source automatically
# ---------------------------------------------------------------------------
# If the full dbt warehouse exists (local dev), read its mart tables. On a
# fresh clone / Streamlit Cloud it won't exist, so fall back to the committed
# parquet snapshots in app/data/. Either way the queries are identical apart
# from the relation name.
USING_WAREHOUSE = DB_PATH.exists()


@st.cache_resource
def get_connection():
    if USING_WAREHOUSE:
        return duckdb.connect(str(DB_PATH), read_only=True)
    return duckdb.connect(":memory:")  # queries hit read_parquet() directly


def _mart(name: str) -> str:
    """SQL relation for a mart: warehouse table locally, parquet file otherwise."""
    if USING_WAREHOUSE:
        return f"main_marts.{name}"
    return f"read_parquet('{(DATA_DIR / (name + '.parquet')).as_posix()}')"


def run_query(sql: str) -> pd.DataFrame:
    return get_connection().execute(sql).fetchdf()


@st.cache_data(ttl=300)
def load_trips_by_time() -> pd.DataFrame:
    return run_query(f"""
        select pickup_date, pickup_hour, iso_week, day_of_week, is_weekend,
               trip_count, total_fare_usd, total_revenue_usd,
               avg_trip_distance_miles, avg_trip_duration_minutes
        from {_mart('fct_trips_by_time')}
        order by pickup_date, pickup_hour
    """)


@st.cache_data(ttl=300)
def load_revenue_by_zone() -> pd.DataFrame:
    return run_query(f"""
        select pickup_location_id, pickup_borough, pickup_zone_name, pickup_service_zone,
               trip_count, total_revenue_usd, total_fare_usd, avg_fare_usd,
               total_tips_usd, avg_total_amount_usd
        from {_mart('fct_revenue_by_pickup_zone')}
        order by total_revenue_usd desc
    """)


@st.cache_data(ttl=300)
def load_payment_type_behavior() -> pd.DataFrame:
    return run_query(f"""
        select payment_type, payment_type_label, trip_count, total_revenue_usd,
               avg_fare_usd, avg_tip_usd, avg_tip_pct, avg_trip_distance_miles,
               avg_trip_duration_minutes, airport_trip_count
        from {_mart('fct_payment_type_behavior')}
        order by trip_count desc
    """)


@st.cache_data(ttl=300)
def load_tip_rate_by_time() -> pd.DataFrame:
    return run_query(f"""
        select day_of_week, day_of_week_num, hour_of_day,
               trip_count, avg_tip_pct, avg_tip_usd, avg_fare_usd,
               cc_trip_count, cc_avg_tip_pct
        from {_mart('fct_tip_rate_by_time')}
        order by day_of_week_num, hour_of_day
    """)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
inject_css()

st.markdown('<div class="mc-header"><span class="mc-logo-dot"></span>'
            '<span class="mc-badge">MetaCTO · Analytics Engineering</span></div>',
            unsafe_allow_html=True)
st.markdown("# NYC Yellow Taxi Analytics")
st.markdown(
    '<div class="mc-sub">Q1 2026 · ~11M trips · powered by <b>dbt-duckdb</b> gold-layer marts. '
    'Medallion pipeline: bronze → silver → gold.</div>',
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4 = st.tabs([
    "Trip Volume Over Time",
    "Revenue by Pickup Zone",
    "Payment Type Analysis",
    "Tip-Rate Heatmap",
])

# =========================================================================
# TAB 1: Trip Volume Over Time
# =========================================================================
with tab1:
    df_time = load_trips_by_time()
    df_time["pickup_date"] = pd.to_datetime(df_time["pickup_date"])

    # KPIs first. Distance/duration are trip-count-weighted means — the mart
    # rows are per-hour averages, so a plain .mean() would average the hourly
    # averages and ignore how many trips each hour carried.
    trips_total = df_time["trip_count"].sum()
    w_distance = (df_time["avg_trip_distance_miles"] * df_time["trip_count"]).sum() / trips_total
    w_duration = (df_time["avg_trip_duration_minutes"] * df_time["trip_count"]).sum() / trips_total

    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, "Total Trips", f"{int(trips_total):,}", accent=True)
    kpi_card(c2, "Total Revenue", f"${df_time['total_revenue_usd'].sum():,.0f}")
    kpi_card(c3, "Avg Distance", f"{w_distance:.1f} mi")
    kpi_card(c4, "Avg Duration", f"{w_duration:.0f} min")

    st.write("")
    st.markdown('<div class="mc-section">Trip Volume Over Time</div>', unsafe_allow_html=True)
    grain = st.radio("Aggregation grain", ["Day", "Week", "Hour of Day"],
                     horizontal=True, key="time_grain", label_visibility="collapsed")

    if grain == "Day":
        agg = df_time.groupby("pickup_date", as_index=False).agg(
            trip_count=("trip_count", "sum"))
        fig = px.area(agg, x="pickup_date", y="trip_count",
                      labels={"pickup_date": "Date", "trip_count": "Trips"},
                      template=PLOTLY_TPL)
        fig.update_traces(line_color=BRAND["orange"], fillcolor="rgba(241,135,0,0.15)")
    elif grain == "Week":
        agg = df_time.groupby("iso_week", as_index=False).agg(
            trip_count=("trip_count", "sum"))
        fig = px.bar(agg, x="iso_week", y="trip_count",
                     labels={"iso_week": "ISO Week", "trip_count": "Trips"},
                     template=PLOTLY_TPL)
        fig.update_traces(marker_color=BRAND["orange"])
    else:
        agg = df_time.groupby("pickup_hour", as_index=False).agg(
            trip_count=("trip_count", "sum"))
        fig = px.bar(agg, x="pickup_hour", y="trip_count",
                     labels={"pickup_hour": "Hour of Day (0–23)", "trip_count": "Trips"},
                     template=PLOTLY_TPL)
        fig.update_traces(marker_color=BRAND["orange"])

    fig.update_layout(hovermode="x unified", height=440)
    st.plotly_chart(fig, width="stretch")

# =========================================================================
# TAB 2: Revenue by Pickup Zone
# =========================================================================
with tab2:
    df_zone = load_revenue_by_zone()

    st.markdown('<div class="mc-section">Revenue by Pickup Zone</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns([2, 2, 3])
    boroughs = ["All"] + sorted(df_zone["pickup_borough"].dropna().unique().tolist())
    borough_filter = fc1.selectbox("Borough", boroughs, key="zone_borough")
    n_zones = fc2.slider("Top N zones", 5, 50, 15, key="top_n_zones")
    sort_metric = fc3.radio("Sort by", ["Total Revenue", "Trip Count", "Avg Fare"],
                            horizontal=True, key="zone_sort")

    dfz = df_zone if borough_filter == "All" else df_zone[df_zone["pickup_borough"] == borough_filter]
    sort_col = {"Total Revenue": "total_revenue_usd", "Trip Count": "trip_count",
                "Avg Fare": "avg_fare_usd"}[sort_metric]
    df_top = dfz.sort_values(sort_col, ascending=False).head(n_zones).sort_values(sort_col)

    fig = px.bar(df_top, x=sort_col, y="pickup_zone_name", orientation="h",
                 labels={sort_col: sort_metric, "pickup_zone_name": ""},
                 hover_data=["pickup_borough", "trip_count", "total_revenue_usd", "avg_fare_usd"],
                 template=PLOTLY_TPL)
    fig.update_traces(marker_color=BRAND["orange"],
                      marker_line_color=BRAND["orange_soft"], marker_line_width=0)
    fig.update_layout(height=max(420, n_zones * 26),
                      title=f"Top {n_zones} Pickup Zones by {sort_metric}")
    st.plotly_chart(fig, width="stretch")

# =========================================================================
# TAB 3: Payment Type Analysis
# =========================================================================
with tab3:
    df_pay = load_payment_type_behavior()

    st.markdown('<div class="mc-section">Payment Type Analysis</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        fig_pie = px.pie(df_pay, values="trip_count", names="payment_type_label",
                         hole=0.55, template=PLOTLY_TPL,
                         color_discrete_sequence=CATEGORICAL)
        fig_pie.update_traces(textposition="outside", textinfo="percent+label")
        fig_pie.update_layout(title="Trip Share by Payment Type", showlegend=False, height=420)
        st.plotly_chart(fig_pie, width="stretch")
    with col2:
        fig_rev = px.bar(df_pay, x="payment_type_label", y="total_revenue_usd",
                         labels={"payment_type_label": "", "total_revenue_usd": "Revenue ($)"},
                         template=PLOTLY_TPL)
        fig_rev.update_traces(marker_color=BRAND["teal"])
        fig_rev.update_layout(title="Total Revenue by Payment Type", height=420)
        st.plotly_chart(fig_rev, width="stretch")

    st.markdown('<div class="mc-section">Behavior Comparison</div>', unsafe_allow_html=True)
    caveat()
    st.dataframe(
        df_pay[["payment_type_label", "trip_count", "avg_fare_usd", "avg_tip_usd",
                "avg_tip_pct", "avg_trip_distance_miles", "avg_trip_duration_minutes",
                "airport_trip_count"]].rename(columns={
            "payment_type_label": "Payment Type", "trip_count": "Trips",
            "avg_fare_usd": "Avg Fare ($)", "avg_tip_usd": "Avg Tip ($)",
            "avg_tip_pct": "Avg Tip %", "avg_trip_distance_miles": "Avg Distance (mi)",
            "avg_trip_duration_minutes": "Avg Duration (min)", "airport_trip_count": "Airport Trips",
        }),
        width="stretch", hide_index=True,
        column_config={"Trips": st.column_config.NumberColumn(format="%d")},
    )

# =========================================================================
# TAB 4: Tip-Rate Heatmap (observed tips; toggle for credit-card-only)
# =========================================================================
with tab4:
    df_tip = load_tip_rate_by_time()

    st.markdown('<div class="mc-section">Tip-Rate Heatmap · Observed Tips</div>',
                unsafe_allow_html=True)
    caveat()

    # Toggle the observability population. "All observed" = credit card +
    # app-hailed Flex Fare (the not-is_cash_tip_unobservable set the mart is
    # built on); "Credit card only" = the cc slice carried in the mart.
    view = st.radio(
        "Population",
        ["All observed tips (card + app-pay)", "Credit card only"],
        horizontal=True, key="tip_view", label_visibility="collapsed",
    )
    if view == "Credit card only":
        pct_col, cnt_col, who = "cc_avg_tip_pct", "cc_trip_count", "credit card only"
    else:
        pct_col, cnt_col, who = "avg_tip_pct", "trip_count", "card + app-pay"

    pivot = df_tip.pivot_table(index="day_of_week", columns="hour_of_day",
                               values=pct_col, aggfunc="mean").reindex(DAY_ORDER)
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=[f"{int(h):02d}:00" for h in pivot.columns], y=pivot.index.tolist(),
        colorscale=HEATMAP_SCALE, colorbar=dict(title="Avg Tip %"),
        hovertemplate="Day: %{y}<br>Hour: %{x}<br>Avg Tip: %{z:.1f}%<extra></extra>",
    ))
    fig.update_layout(template=PLOTLY_TPL,
                      title=f"Average Tip % by Day of Week × Hour · {who}",
                      xaxis_title="Hour of Day", yaxis_title="", height=440)
    st.plotly_chart(fig, width="stretch")

    with st.expander("Trip count by time slot (confidence weighting)"):
        pivot_c = df_tip.pivot_table(index="day_of_week", columns="hour_of_day",
                                     values=cnt_col, aggfunc="sum").reindex(DAY_ORDER)
        fig_c = go.Figure(data=go.Heatmap(
            z=pivot_c.values, x=[f"{int(h):02d}:00" for h in pivot_c.columns], y=pivot_c.index.tolist(),
            colorscale="Teal", colorbar=dict(title="Trips"),
            hovertemplate="Day: %{y}<br>Hour: %{x}<br>Trips: %{z:,.0f}<extra></extra>",
        ))
        fig_c.update_layout(template=PLOTLY_TPL, title=f"Trip count by Day × Hour · {who}",
                            xaxis_title="Hour of Day", yaxis_title="", height=400)
        st.plotly_chart(fig_c, width="stretch")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.write("")
st.markdown(
    f'<div style="border-top:1px solid {BRAND["border"]};padding-top:14px;'
    f'color:{BRAND["text_muted"]};font-size:0.85rem;">'
    'Built as the MetaCTO Senior Data Engineer assessment · '
    '<a href="https://github.com/jcandrade25/nyc-taxi-analytics" target="_blank">Repository</a> · '
    'Architecture in PLAN.md</div>',
    unsafe_allow_html=True,
)
