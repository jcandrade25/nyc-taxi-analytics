# NYC Yellow Taxi Analytics

An analytics-engineering project that takes raw NYC TLC yellow-taxi trip
records (Jan–Mar 2026, ~11M rows) and turns them into a small set of
trusted, business-facing facts powering a Streamlit dashboard.

Built as the **[MetaCTO Senior Data Engineer technical
assessment](resources/Technical%20AI%20Assessment%20—%20Data.txt)**.
Architecture, decisions, trade-offs, and the as-built record are
documented in **[PLAN.md](PLAN.md)**. Project rules and the
prompt-logging convention are in **[CLAUDE.md](CLAUDE.md)**.

---

## What this is

```
                     ┌──────────────────────────────────┐
   resources/        │  3× yellow_tripdata_2026-MM.parquet  │
   (raw, public)     │  taxi_zone_lookup.csv (265 rows)     │
                     └──────────────────┬───────────────┘
                                        │   read_parquet() / read_csv_auto()
                                        ▼
   ┌─── BRONZE ──── models/staging/     (views, snake_case, typed)
   │                                    │
   │    SILVER ──── models/intermediate/ (tables: cleansed → deduped → enriched)
   │                                    │
   └─── GOLD ────── models/marts/        (tables: dims + 4 pre-aggregated facts)
                                        │
                                        ▼
                            app/streamlit_app.py
                  (reads dev.duckdb read-only, Plotly charts)
```

Stack: **dbt-duckdb** locally (Snowflake-portable by construction —
see PLAN.md §1), **DuckDB** as the warehouse, **Streamlit + Plotly**
for the dashboard.

The four dashboard visualizations:

1. **Trip Volume Over Time** — single `fct_trips_by_time` mart at hour
   grain, Streamlit picks day/week/hour `GROUP BY` at query time.
2. **Revenue by Pickup Zone** — top-performing zones, sortable.
3. **Payment Type Analysis** — rider-behavior differences across the
   seven TLC payment codes.
4. **Tip-Rate Heatmap** — average tip percent by hour-of-day ×
   day-of-week, **credit-card-only** (`payment_type = 1`) with an
   in-chart cash-tip caveat. See PLAN.md §5 and `docs/caveats.md`.

---

## Quickstart

Prereqs: Python 3.10–3.12 (dbt-core 1.9 does not yet support 3.13/3.14),
git, ~200 MB of disk for the warehouse file once built.

```bash
# 1. clone
git clone https://github.com/jcandrade25/nyc-taxi-analytics.git
cd nyc-taxi-analytics

# 2. virtualenv + deps
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. dbt profile (gitignored — copy the example)
cp profiles.yml.example profiles.yml
export DBT_PROFILES_DIR=$(pwd)    # Windows PowerShell: $env:DBT_PROFILES_DIR = (Get-Location).Path

# 4. dbt build
dbt deps
dbt seed
dbt build                          # full bronze → silver → gold + tests

# 5. dashboard
streamlit run app/streamlit_app.py
```

The full build takes ~50 s on a laptop. After it completes,
`dev.duckdb` sits next to the project (~2 GB — the three silver tables
plus `fct_trips` each hold ~11M rows); the Streamlit app opens it
read-only.

---

## Deploy to Streamlit Community Cloud

The app **self-initializes**: `app/streamlit_app.py` checks for
`dev.duckdb` on startup and, if it's missing (as on a fresh Cloud
deploy), runs `dbt deps` + `dbt build` via subprocess before loading the
dashboard. The raw parquet/CSV sources are committed to the repo, so no
manual setup is needed.

To deploy:

1. Push this repo to GitHub (public).
2. On [share.streamlit.io](https://share.streamlit.io), create an app from
   the repo with **Main file path** = `app/streamlit_app.py`.
3. In **Advanced settings**, set **Python version = 3.12** (dbt-core 1.9
   does not import on 3.13/3.14).
4. Deploy. The first boot runs the dbt build (~1–2 min behind a status
   panel); subsequent boots reuse the warehouse.

> **Resource note.** The full dataset materializes ~40M rows across the
> silver/gold tables and the warehouse file reaches ~2 GB. Streamlit
> Community Cloud's free tier (~1 GB RAM) may struggle with the
> first-boot build. If the build OOMs or times out, the cheapest fix is
> to load **one month** instead of three — set the `TAXI_PARQUET_GLOB`
> env var (or edit `parquet_glob` in `dbt_project.yml`) to a single
> file. The pipeline is identical; only the row count changes.

---

## Browsing the models

```bash
dbt docs generate
dbt docs serve                    # http://localhost:8080
```

The lineage graph terminates at the Streamlit exposure
(`streamlit_taxi_dashboard`) so you can see, per mart, which
dashboard chart depends on it. The `caveat__cash_tip_invisibility`
and `caveat__store_and_fwd_dedupe` doc blocks render verbatim
wherever they're referenced — one place to edit, many places to
appear.

---

## Project layout

```
.
├── CLAUDE.md                project rules (prompt logging, conventions)
├── PLAN.md                  architecture, decisions, trade-offs, as-built record
├── README.md                this file
├── dbt_project.yml          dbt config + per-layer materialization defaults
├── packages.yml             dbt_utils, dbt_expectations (via git URLs)
├── profiles.yml.example     template for the local DuckDB profile
├── requirements.txt         Python deps (dbt-duckdb, streamlit, plotly, …)
├── prompts.txt              chronological log of every prompt + response
├── resources/               raw TLC data (parquet) + zone lookup + dictionary
├── app/
│   └── streamlit_app.py     MetaCTO-themed dashboard (self-initializing)
├── .streamlit/
│   └── config.toml          Streamlit theme config
├── models/
│   ├── staging/             bronze: typed views over sources
│   ├── intermediate/        silver: cleansed → deduped → enriched
│   └── marts/               gold: facts/dims + Streamlit exposure
├── seeds/                   payment_types.csv, rate_codes.csv
├── tests/                   singular SQL tests (business invariants)
├── macros/                  custom Jinja (none yet)
├── snapshots/               SCD2 (none — see PLAN.md §7)
├── analyses/                ad-hoc SQL (none)
└── docs/                    dbt doc blocks (__overview, caveats)
```

---

## Conventions

From [CLAUDE.md](CLAUDE.md):

- **SQL**: `snake_case` columns, explicit casting, CTEs over
  subqueries. Monetary columns `DECIMAL(10,2)` at row grain,
  `DECIMAL(18,2)` at mart aggregates (see PLAN.md §2 for why).
- **dbt**: `ref()` over hardcoded table names, generic tests in
  YAML, singular tests in `tests/`.
- **Materializations**: staging = views, intermediate = tables (see
  PLAN.md §2 for why not ephemeral), marts = tables.
- **Git**: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`).
- **Time zone**: all timestamps are NYC local. No UTC conversion
  anywhere — see PLAN.md §6.

---

## What this is NOT (scope guard)

No incremental models, no snapshots, no CI/CD, no PII handling, no
green/FHV data. PLAN.md §7 lists each omission with reasoning. For a
production migration, PLAN.md §1 outlines the actual lift to
Snowflake (profile swap + schema-strategy review + source-binding
rewrite).
