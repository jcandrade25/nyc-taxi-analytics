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

Prereqs: Python 3.10–3.12 for the full dbt build (dbt-core 1.9 does not
yet support 3.13/3.14), git, ~2 GB of disk for the warehouse file once
built.

```bash
# 1. clone
git clone https://github.com/jcandrade25/nyc-taxi-analytics.git
cd nyc-taxi-analytics

# 2. virtualenv + dev deps (dashboard + dbt)
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

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

> **Just want the dashboard?** Install the lighter `requirements.txt`
> (no dbt) and run `streamlit run app/streamlit_app.py`. With no
> `dev.duckdb` present, the app reads the committed mart snapshots in
> `app/data/` — the same way the Cloud deploy works.

---

## Deploy to Streamlit Community Cloud

The deployed app does **not** run dbt or build a warehouse at runtime —
that would exceed the free tier's memory. Instead it reads the four
dashboard marts from committed parquet snapshots in `app/data/`
(generated locally by `python export_marts.py` after a `dbt build`). The
charts still show the full three-month dataset; only the heavy ~11M-row
intermediate tables are left out, since no chart needs them.

To deploy:

1. Push this repo to GitHub (public).
2. On [share.streamlit.io](https://share.streamlit.io), create an app from
   the repo with **Main file path** = `app/streamlit_app.py`.
3. Deploy. Boot is near-instant — Cloud installs the lightweight
   `requirements.txt` (Streamlit/Plotly/pandas/DuckDB; no dbt) and the
   app reads the parquet marts directly. Python 3.12 is recommended (it's
   what the pins are verified against), but there's no dbt import
   constraint at runtime.

### Refreshing the deployed data

The committed marts are a point-in-time snapshot. To update them after
changing models:

```bash
dbt build              # rebuild dev.duckdb (needs requirements-dev.txt)
python export_marts.py # re-export app/data/*.parquet
git commit -am "chore: refresh mart snapshots" && git push
```

Streamlit Cloud redeploys on push.

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
├── requirements.txt         dashboard runtime deps (Streamlit Cloud; no dbt)
├── requirements-dev.txt     runtime + dbt-core/dbt-duckdb for local builds
├── export_marts.py          re-export app/data/*.parquet from dev.duckdb
├── prompts.txt              chronological log of every prompt + response
├── resources/               raw TLC data (parquet) + zone lookup + dictionary
├── app/
│   ├── streamlit_app.py     MetaCTO-themed dashboard (warehouse or parquet)
│   └── data/                committed mart snapshots the Cloud app reads
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
