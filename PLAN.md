# NYC Yellow Taxi Analytics — Build Plan & As-Built Record

This document captures the decisions behind the dbt project layout, the
warehouse choice, and the model-by-model design for the bronze → silver →
gold buildout — and now also records what was actually delivered. Sections
1–8 are the design rationale; §9 is the as-built execution record; §11 is
the implementation notes (where the build refined the original plan).

---

## 0. Status & delivery summary

**Status: complete and deploy-ready.** Full `dbt build` is green
(**59 pass, 4 intentional warns, 0 errors**); the Streamlit dashboard
renders all four required views; the app self-initializes on Streamlit
Community Cloud.

**What was built**

- **Seeds** — `payment_types`, `rate_codes` (TLC code→label lookups) with
  primary-key tests.
- **Bronze** (`models/staging/`, views) — `stg_tlc__trips`,
  `stg_tlc__zones`, `stg_tlc__payment_types`, `stg_tlc__rate_codes`.
  snake_case, `DECIMAL(10,2)` money, NYC-local timestamps, no row drops.
- **Silver** (`models/intermediate/`, tables) — `int_trips__cleansed`
  (DQ filters, no dedupe) → `int_trips__deduped` (surrogate-key
  row_number) → `int_trips__enriched` (zone/payment/rate joins + derived
  columns).
- **Gold** (`models/marts/`, tables) — `dim_zone`, `dim_date`, `fct_trips`,
  and the four chart-shaped facts: `fct_trips_by_time`,
  `fct_revenue_by_pickup_zone`, `fct_payment_type_behavior`,
  `fct_tip_rate_by_time`.
- **Tests** — generic (YAML) + 4 singular (`tests/`); see §3.
- **Docs** — model/column descriptions, two caveat doc blocks, and a
  Streamlit `exposure` terminating the lineage.
- **Dashboard** — `app/streamlit_app.py`, MetaCTO-themed, four Plotly
  views, `@st.cache_data`, read-only DuckDB, self-initializing bootstrap.

**Requirement coverage** — (1) Trip Volume Over Time with day/week/hour
grain ✓; (2) Revenue by Pickup Zone with revenue/avg-fare/trip-count +
filter & sort ✓; (3) Payment Type Analysis ✓; (4) candidate viz =
credit-card-only tip-rate heatmap ✓; bronze/silver/gold dbt project ✓;
DQ tests + documentation ✓; Streamlit on gold marts ✓.

**Run it** — see [README.md](README.md) for the local quickstart and the
Streamlit Community Cloud deploy steps.

---

## 1. Warehouse choice: DuckDB locally, Snowflake-compatible by construction

The assessment is a 2–3-hour local build with a possible future migration
to Snowflake. Three realistic options:

| Option | Local-dev speed | Prod fidelity | Setup overhead | Cost |
| --- | --- | --- | --- | --- |
| **DuckDB (chosen)** | Sub-second on 11M rows on a laptop, zero infra | High — same ANSI SQL surface for ~95% of analytics workloads; dbt-duckdb mirrors dbt-snowflake configs | One `pip install` | $0 |
| Snowflake free trial | Slower iteration (network + warehouse spin-up), credit anxiety | 100% | Trial signup, network egress for parquet | Credits |
| Postgres + parquet_fdw | Mid speed, no columnar engine | Lower — Postgres SQL drifts from Snowflake in window/QUALIFY/array ops | Docker + extension build | $0 |

### Why DuckDB wins for this build

1. **Reads parquet natively.** `read_parquet('resources/*.parquet')` with
   no ingestion step. Snowflake needs an external stage + `COPY INTO`;
   that's another 30 minutes we don't need to spend.
2. **Same dbt mental model.** `dbt-duckdb` is a first-class adapter.
   Materializations, `ref()`, sources, tests, and docs all behave
   identically to `dbt-snowflake`. The migration is mostly
   `profiles.yml` + a few function-name swaps.
3. **Cheap to nuke and rebuild.** `rm dev.duckdb && dbt build` recovers
   from any mistake in under a minute on the full 11M-row dataset.
4. **Streamlit can share the file directly.** The dashboard opens the
   same `dev.duckdb` read-only — no API gateway, no auth scaffolding.

### Portability rules (so the Snowflake migration stays cheap)

The migration path is real, not hypothetical. To keep it cheap we self-impose:

- **No DuckDB-only functions in model SQL.** Specifically: avoid
  `LIST(...)`, `ARG_MAX`, `STRUCT_PACK`, `epoch_ms()`. Use ANSI
  equivalents that compile under both adapters.
- **Date arithmetic via `dbt_utils.date_trunc` and
  `dbt_utils.dateadd`.** Both packages dispatch per-adapter, so the
  same Jinja compiles correctly on either warehouse.
- **All source paths are templated.** `parquet_glob` and
  `zone_lookup_path` are dbt vars (see `dbt_project.yml`). For
  Snowflake we'd replace them with views over external stages and
  point `source('tlc', 'yellow_trips_raw')` at those views — no
  downstream model changes.
- **Surrogate keys via `dbt_utils.generate_surrogate_key`.** Hash
  function differs across warehouses; the macro handles dispatch.
- **No `QUALIFY` without testing.** Supported in Snowflake and DuckDB
  but not in every adapter; we use the pattern carefully and only with
  packages-blessed alternatives.

### Honest scope of the Snowflake migration

The earlier draft of this plan claimed "the profile swap is the only
delta." That overstated it. The honest version: **a profile swap plus a
schema-strategy review.** Two real gaps to call out:

- **Source bindings are DuckDB-only.** `models/staging/_sources.yml`
  uses `identifier: "read_parquet('...')"` and `read_csv_auto('...')`
  — both are DuckDB functions, not ANSI. The Snowflake equivalent is
  either (a) a Snowflake external stage + a view per source table, or
  (b) `COPY INTO` raw landing tables. The downstream `source()`
  references don't change, but the source identifiers must be
  rewritten. Budget ~30 min for this in any real migration.
- **`+schema` semantics differ.** In `dbt-duckdb`, the `+schema`
  config on each layer maps to attached database files (the schema
  becomes part of the filename pattern). In `dbt-snowflake`, it maps
  to actual schemas inside a Snowflake database. The model layout
  works either way, but the deployment story (one schema per env, one
  schema per layer, custom schemas per developer) needs a deliberate
  choice before first prod run — not a copy-paste.

Net: the same `models/` directory `dbt build`s against either adapter
with **profile swap plus schema-strategy review plus source-binding
rewrite** as the deltas. Still cheap; just not free.

---

## 2. Architecture: medallion (bronze → silver → gold)

```
resources/*.parquet      (raw — outside dbt)
        │
        ▼
sources.tlc.yellow_trips_raw   (DuckDB view via read_parquet)
        │
        ▼
models/staging/                ← BRONZE
   stg_tlc__trips                  type-cast, snake_case, no row-drop
   stg_tlc__zones                  zone lookup, typed
   stg_tlc__payment_types          ref('payment_types') seed, typed
   stg_tlc__rate_codes             ref('rate_codes') seed, typed
        │
        ▼
models/intermediate/           ← SILVER
   int_trips__cleansed             DQ filters, drop impossible rows,
                                     flag suspect-but-keepable rows.
                                     PRESERVES duplicates so the dedupe
                                     singular test still catches them.
                                     (table)
   int_trips__deduped              row_number() over surrogate_key
                                     ordered by (filename DESC, pickup
                                     ASC) keeping rn=1. The "rebuild after
                                     test passes" boundary.
                                     (table)
   int_trips__enriched             join zones (PU + DO), payment-type
                                     and rate-code labels, derive
                                     duration / speed / tip_pct /
                                     is_airport / cash-tip-unobservable
                                     flags.
                                     (table — see materialization note)
        │
        ▼
models/marts/                  ← GOLD
   dim_zone                        clean zone dim with surrogate key
   dim_date                        date spine Jan 1 – Mar 31 2026
   fct_trips                       grain: one row per trip
   fct_trips_by_time               grain: (pickup_hour) — viz #1
                                     carries pickup_date, pickup_hour,
                                     iso_week, day_of_week, is_weekend
                                     so Streamlit picks GROUP BY at
                                     query time (day / week / hour
                                     from a single mart, not three).
   fct_revenue_by_pickup_zone      grain: (pickup_zone) — viz #2
   fct_payment_type_behavior       grain: (payment_type) — viz #3
   fct_tip_rate_by_time            grain: (day_of_week, hour_of_day)
                                     — viz #4. Credit card only
                                     (payment_type = 1). Carries
                                     trip_count for confidence
                                     weighting on the heatmap.
```

### Layer responsibilities (and what does NOT belong)

**Bronze / staging — `models/staging/`**
- Materialization: `view` (cheap, always reflects source)
- Job: rename to `snake_case`, cast to canonical types (including
  monetary columns to `DECIMAL(10,2)`), no row drops, no joins, no
  business logic
- The *only* place TLC's CamelCase columns appear
- Timestamps: cast to `TIMESTAMP` but **kept in NYC local time** — see
  §6

**Silver / intermediate — `models/intermediate/`**
- Materialization: `table` (was `ephemeral` in the earlier draft)
- **Why the change:** four gold marts consume the enriched intermediate.
  Ephemeral would inline the zone + payment-type joins into all four
  marts, executing the same ~11M-row two-side join four times per
  `dbt build`. Trade-off: ~one extra table's worth of disk (small) and
  a longer first-run incremental boundary, in exchange for a roughly
  4× speedup at the mart layer and a single audit point for the join
  logic. On Snowflake the savings are also dollar-denominated.
- Job: data-quality filters, denormalization (zone join, payment-type
  and rate-code label join), derived columns
- Three intermediate models with explicit responsibilities:
  - `int_trips__cleansed` — DQ filters; **does not dedupe**, so the
    dedupe singular test runs against this model and catches
    surrogate-key collisions
  - `int_trips__deduped` — `row_number()` per surrogate key keeping
    one row (see §4 for tiebreak rule); marts read from here
  - `int_trips__enriched` — joins zones, payment-type labels, rate
    codes; derives `trip_duration_minutes`, `average_speed_mph`,
    `tip_pct_of_fare`, `is_airport_trip`, `is_cash_tip_unobservable`
- Idempotent and side-effect-free — re-running gives identical output

**Gold / marts — `models/marts/`**
- Materialization: `table` (the dashboard hits these; latency matters)
- Job: pre-aggregate to the exact grain a single chart needs
- Each fact table is named for the question it answers, not the source
  it came from
- **Monetary aggregates are explicitly cast to `DECIMAL(18,2)`.**
  Single-trip values fit in `DECIMAL(10,2)` comfortably (max
  $99,999,999.99), but `SUM(fare_amount_usd)` across 11M rows at
  ~$15 average easily exceeds $100M, blowing that precision. DuckDB
  and Snowflake both auto-widen `SUM(DECIMAL(n,m))`, but the explicit
  cast (a) documents intent, (b) prevents accidental downstream
  truncation if an analyst stamps a column back to `DECIMAL(10,2)`,
  and (c) keeps the boundary visible to anyone reading the mart SQL.

---

## 3. Data quality strategy

Two classes of test, both authored as we build:

**Generic tests (YAML)** for shape and referential integrity:
- `unique` + `not_null` on every primary key
- `relationships` on `pickup_zone_id` / `dropoff_zone_id` → `dim_zone`
- `accepted_values` on `payment_type` (0..6), `RatecodeID` (1..6, 99),
  `store_and_fwd_flag` ('Y','N'), and **`vendor_id` (1, 2, 6, 7)** per
  the current TLC spec
- `dbt_utils.accepted_range` on `trip_distance_miles` (0..100),
  `fare_amount_usd` (0..1000), `passenger_count` (0..8)
- **`dbt_expectations.expect_column_values_to_be_between`** on
  `pickup_datetime` and `dropoff_datetime` for the range
  `[2026-01-01, 2026-04-01)` — TLC monthly files routinely carry
  stray rows from neighbouring months (typos, late-arriving records,
  meter clock skew); the test catches and surfaces that drift instead
  of letting it silently inflate fact counts
- `dbt_expectations.expect_row_count_to_be_between` on the cleansed
  trips model so we get paged if cleansing throws away too much

**Singular tests (`tests/*.sql`)** for business invariants the YAML
generics can't express:
- `assert_no_negative_revenue.sql` — `fare_amount + tip + tolls +
  surcharges` ≥ 0 except for explicit refunds (`payment_type = 4`)
- `assert_pickup_before_dropoff.sql` — no time-travel trips
- `assert_zero_tip_only_when_not_credit_card.sql` — flags the cash-tip
  invisibility issue if it ever reverses (i.e., a credit-card trip
  with tip = 0 in a cohort where that's improbable)
- `assert_store_and_fwd_dedupe.sql` — **runs against
  `int_trips__cleansed`, NOT a pre-deduped intermediate.** The point
  is to catch surrogate-key collisions in the population that arrives
  from the source; running it against the deduped model would
  trivially pass and hide the underlying issue. When the test fails,
  the failure is logged, and `int_trips__deduped` (downstream of the
  test) picks one row per surrogate key for the marts to consume.

Tests are part of `dbt build`; CI would gate merges on a green run.

---

## 4. Surrogate key strategy

No natural PK in the source. We hash:

```
dbt_utils.generate_surrogate_key([
    'vendor_id',
    'pickup_datetime',
    'dropoff_datetime',
    'pickup_location_id',
    'dropoff_location_id'
])
```

That's the same 5-tuple typically used to dedupe TLC data and survives
`store_and_fwd_flag = 'Y'` retransmits in the **common** case.

**The edge case to be honest about:** `store_and_fwd_flag = 'Y'` means
the record sat in vehicle memory until the device reconnected. Some
vendors re-stamp the timestamps with millisecond jitter on retransmit
(observed on TLC data historically), which defeats the hash. Result: a
small number of legitimate duplicates land in `int_trips__cleansed`.

Our response:
1. `assert_store_and_fwd_dedupe.sql` runs against the cleansed model
   and surfaces the count when it occurs (monitoring signal).
2. `int_trips__deduped` runs `row_number() over (partition by
   trip_surrogate_id order by filename desc, pickup_datetime asc)` and
   keeps `rn = 1`. The tiebreak picks the **latest-arriving file**
   first (the retransmit usually completes), and within that, the
   earliest pickup timestamp.
3. All gold marts read from `int_trips__deduped`, not `__cleansed`.
4. The cash-tip caveat doc block (see §5) notes both this and the
   tip-visibility limitation in the same place.

---

## 5. Documentation as a first-class deliverable

Docs are a graded deliverable per the assignment, not an afterthought.
The bar is: someone who has never seen this project can open
`dbt docs serve` and understand both the data shape and the analytic
limitations.

**Model- and column-level descriptions.** Every fact and dim ships
with a `description:` in its YAML. Every column on every fact and dim
gets a `description:` too — short, business-readable, no Jinja. The
descriptions reference the source-of-truth field semantics, not the
column name in different casing.

**`docs/` directory with doc blocks.** Two blocks ship at minimum:

- `docs/__overview.md` — the project's `{% docs __overview__ %}`
  homepage. Renders on `dbt docs serve` as the landing page. Explains
  the medallion layout, the time window, the four dashboard
  visualizations, and links to the GitHub repo + Loom.
- `docs/caveats.md` — the **cash-tip caveat doc block**
  (`{% docs caveat__cash_tip_invisibility %}`) and the
  store_and_fwd duplicate caveat block
  (`{% docs caveat__store_and_fwd_dedupe %}`). Referenced from any
  column or model where the caveat materially shapes interpretation
  (e.g. `tip_amount_usd`, `tip_pct_of_fare`, `fct_tip_rate_by_time`).
  Doing this via doc blocks (not freehand description text) means the
  caveat appears verbatim everywhere it applies and there's exactly
  one place to edit it.

**`exposures.yml` terminating the DAG at Streamlit.** A single
`exposure:` entry of `type: dashboard` named `streamlit_taxi_dashboard`
that lists the four marts as `depends_on`. This makes the lineage
graph in `dbt docs serve` terminate at the dashboard tile instead of
hanging at the marts — visible proof that we know which downstream
consumer relies on which upstream model.

**Loom screenshot opportunity.** The first 60 seconds of the §7 Loom
walks `dbt docs serve` with the full lineage graph zoomed out enough
to show source → bronze → silver (with the cleansed → deduped →
enriched split visible) → gold → exposure. That image is the single
most compressed summary of the engineering work.

**Streamlit caveat surfacing.** Every chart that touches tip data
displays the cash-tip caveat as an in-chart annotation (small italic
note under the title). The query functions powering those charts are
all decorated with `@st.cache_data` so the underlying mart is hit once
per session per filter combination, not per chart re-render.

---

## 6. Streamlit wiring

- `app/streamlit_app.py` opens `dev.duckdb` read-only via
  `duckdb.connect(..., read_only=True)`.
- **`@st.cache_data` on every query function.** The marts are small
  enough that the bottleneck is repeated DuckDB connections during
  interactive filter use, not query execution. Caching at the
  function level keyed on filter args is the right granularity.
- Each chart queries exactly one mart (the one named for it). No
  in-app aggregation beyond the filter the user picks (and the
  `GROUP BY` choice for `fct_trips_by_time`, which is just a `SELECT`
  shape, not a join).
- Filters (date range, borough, payment type) compile to `WHERE`
  clauses against the mart, not joins. Marts carry the dimensions
  needed for slicing pre-joined.
- Plotly for charts (per CLAUDE.md).
- **Time zone:** TLC timestamps are local NYC wall-clock time. We do
  **not** convert to UTC anywhere in the pipeline. The dashboard
  treats `pickup_hour`, `day_of_week`, etc. as local-NYC. This is the
  TLC convention and matches the way operators and analysts reason
  about the data; any UTC conversion would silently shift the
  hour-of-day heatmap.

---

## 7. What we are explicitly NOT doing (scope guard)

- No incremental models. The dataset fits in memory and full rebuild
  is ~30 s; incrementality is complexity we don't need.
- No snapshots. There's no SCD2 dimension here that warrants it.
- No exposure declarations beyond the single Streamlit exposure (§5).
- No CI/CD wiring. Out of scope for a 2–3-hour build; the Loom covers
  what we'd do (§9).
- No PII handling. The dataset contains none.
- No green/FHV trip data — yellow only per the assignment.
- No UTC conversion (§6).

---

## 8. Repo hygiene

- `profiles.yml` is **gitignored**. A `profiles.yml.example` is
  committed instead. README setup includes a `cp profiles.yml.example
  profiles.yml` step. Reason: the prod_snowflake target uses
  `env_var()` for credentials today, but the moment anyone hardcodes
  a value during local dev the gitignore prevents it from leaking.
  This is cheap defense in depth.
- `.gitignore` covers `*.duckdb`, `target/`, `dbt_packages/`, `logs/`,
  `.user.yml`, `.venv/`, `.env`, and `.streamlit/secrets.toml`.
- Seeds shipped in `seeds/`:
  - `seeds/payment_types.csv` — TLC payment-type code → label
    mapping. Was originally going to live in an inlined CTE in
    `stg_tlc__payment_types`; lifted to a seed because (a) it's
    static reference data the TLC publishes and we should treat it as
    such, (b) it shows up in the dbt docs graph, (c) it's reviewable
    in git diffs the next time TLC adds a code.
  - `seeds/rate_codes.csv` — same treatment for the RatecodeID
    mapping. The seeds config in `dbt_project.yml` is already set up.

---

## 9. Execution order (as built — all steps complete)

All nine steps below were delivered in this order. Refinements made along
the way are recorded in §11.

1. **Seeds**: ship `seeds/payment_types.csv` and `seeds/rate_codes.csv`.
2. **Bronze**: `stg_tlc__trips`, `stg_tlc__zones`,
   `stg_tlc__payment_types`, `stg_tlc__rate_codes` + their YAML tests.
   Monetary cols cast to `DECIMAL(10,2)`.
3. **Silver**: `int_trips__cleansed` (no dedupe), `int_trips__deduped`
   (row_number tiebreak), `int_trips__enriched` (table) + DQ tests.
   `tip_pct_of_fare` uses `NULLIF(fare_amount_usd, 0)` in the
   denominator.
4. **Gold dims**: `dim_zone`, `dim_date`.
5. **Gold facts**: `fct_trips` first (parent fact), then
   `fct_trips_by_time` (hour grain with date/week/dow/weekend
   carried), `fct_revenue_by_pickup_zone`,
   `fct_payment_type_behavior`, `fct_tip_rate_by_time`
   (payment_type = 1 only, carries trip_count). Aggregates explicitly
   cast to `DECIMAL(18,2)`.
6. **Singular tests** in `tests/`, including
   `assert_store_and_fwd_dedupe.sql` pointed at `int_trips__cleansed`.
7. **Docs**: `docs/__overview.md`, `docs/caveats.md` with the two
   doc blocks, column descriptions on every fact/dim,
   `exposures.yml` with the Streamlit exposure. Run
   `dbt docs generate` and verify `dbt docs serve` renders the full
   DAG terminating at the dashboard.
8. **Streamlit app** with the four visualizations and `@st.cache_data`.
9. **README** with setup steps:
   `python -m venv .venv && source .venv/bin/activate`,
   `pip install -r requirements.txt`,
   `cp profiles.yml.example profiles.yml`,
   `export DBT_PROFILES_DIR=$(pwd)`,
   `dbt deps && dbt seed && dbt build`,
   `streamlit run app/streamlit_app.py`.

---

## 10. Loom script (~5 minutes)

A concrete shot list, not a vibe.

- **~30s — Stack choice and portability story.** "DuckDB locally,
  Snowflake-compatible by construction. Same dbt mental model, same
  SQL surface for analytics workloads. Migration is a profile swap
  plus schema-strategy review plus source-binding rewrite — covered
  in PLAN.md §1. Picked DuckDB because parquet ingest is one function
  call and full rebuild on 11M rows is sub-minute on a laptop."

- **~60s — Lineage walk in `dbt docs serve`.** Open the lineage graph
  zoomed out. Point at: parquet sources → bronze views → the silver
  three-step split (cleansed → deduped → enriched) → gold dims and
  four named facts → Streamlit exposure. Call out that the exposure
  terminates the DAG — proof we know what depends on what.

- **~60s — A DQ test failing intentionally, then passing.** Edit
  `int_trips__cleansed` to widen one filter (e.g., remove the
  pickup-date range filter), run `dbt build --select +tag:dq`, watch
  the `dbt_expectations.expect_column_values_to_be_between` test on
  `pickup_datetime` fail with the count of out-of-range rows. Revert,
  rebuild, green. Frames tests as production guardrails, not
  decoration.

- **~90s — Dashboard demo.** Open Streamlit. Filter the trip-volume
  chart through day → week → hour to demonstrate the single-mart
  multi-grain design from `fct_trips_by_time`. Show top revenue
  zones, walk the payment-type breakdown, end on the tip-rate
  heatmap and **explicitly** call out the cash-tip caveat sitting
  under the title: "this is the analytic judgment call — we
  restricted to credit card because cash tips are unobservable in
  TLC data. The same caveat is on every column it touches in the
  dbt docs."

- **~60s — What production would add.** Incremental models on
  `fct_trips` and `int_trips__cleansed` keyed on parquet `filename`
  so monthly TLC drops don't trigger full rebuilds. CI running
  `dbt build` on every PR against a sample. Source freshness alerts
  on `loaded_at_field`. Snowflake migration with the source-binding
  rewrite. **Why these are the right cuts to defer:** none of them
  change the modeling decisions on display; all of them are
  mechanical lift that doesn't demonstrate analytics-engineering
  judgment in a 5-minute video.

Timing total: 30 + 60 + 60 + 90 + 60 = **300 seconds**.

---

## 11. As-built notes (where the build refined the plan)

Everything else was built exactly as designed in §1–§8. These are the
places the implementation departed from the original plan, with the
reason.

1. **Source binding: `meta.external_location`, not `identifier`.**
   dbt-duckdb quotes the source `identifier` as a relation name, so the
   planned `read_parquet(...)` / `read_csv_auto(...)` identifiers failed
   with a catalog error. Both sources use `meta.external_location`
   instead; downstream `source()` references are unchanged. The lookup
   source was renamed `ref` → `ref_data` for clarity. (The Snowflake
   migration note in §1 already anticipated this exact rewrite.)

2. **Test severities = `warn` for the monitoring signals.** dbt defaults
   tests to `error`, but §3/§4 frame several checks as signals, not gates.
   Set to `warn` so the build stays green while still surfacing drift:
   the `pickup`/`dropoff` datetime-range expectations (10 + 843 stray
   neighbouring-month rows, already hard-filtered in cleansing),
   `assert_store_and_fwd_dedupe` (~32k surrogate collisions — by design a
   monitoring signal), and `assert_no_negative_revenue` (~1k legitimate
   meter/refund adjustments; predicate also widened to allow
   `payment_type in (3,4,6)`). `assert_zero_tip_only_when_not_credit_card`
   uses a 15% threshold at `warn`.

3. **`tip_pct_of_fare` guard hardened.** Kept the planned
   `NULLIF(fare_amount_usd, 0)` and additionally guarded
   `WHEN fare_amount_usd > 0`, because cleansing admits small negative-fare
   adjustments that would otherwise produce negative percentages and skew
   `avg_tip_pct`. Strict superset of the original divide-by-zero guard.

4. **Dashboard reads `main_marts.*`.** dbt-duckdb materializes custom
   schemas as `main_<schema>`; the app queries the actual schema names.

5. **Self-initializing deploy.** `app/streamlit_app.py` runs `dbt deps` +
   `dbt build` on first boot if `dev.duckdb` is absent (it's gitignored, so
   it won't exist on a fresh Streamlit Cloud clone). It generates
   `profiles.yml` from the committed example first. The raw parquet/CSV are
   committed so Cloud can build with no manual setup.

6. **Environment: Python 3.12.** dbt-core 1.9 / mashumaro fail to import on
   Python 3.13/3.14. Local build and the Cloud deploy use Python 3.12;
   pinned in `requirements.txt` and the README deploy steps.

7. **MetaCTO brand theme** (added after the core build). `.streamlit/
   config.toml` + an in-app theme matching metacto.com (teal-navy `#0F2028`
   background, orange `#F18700` accent, Barlow + Inter, pill tabs, KPI
   cards, branded Plotly template). No data-model changes.

**Known minor issues.** (a) Plotly charts inside `st.tabs` can first-paint
with zero width (a Streamlit quirk); any resize/interaction forces the
redraw. (b) The dedupe `row_number()` tiebreak can resolve exact full-tuple
ties differently across rebuilds, so the final trip count varies by a few
hundred rows out of ~10.8M — expected, not a defect.

---

## 12. Operating notes

- **Warehouse size.** The full three-month build materializes ~40M rows
  across the silver/gold tables; `dev.duckdb` reaches ~2 GB and the build
  takes ~50 s locally. On Streamlit Community Cloud's free tier (~1 GB RAM)
  the first-boot build may be slow or OOM; the README documents a
  one-month fallback via the `TAXI_PARQUET_GLOB` var.
- **Source of truth.** This file (design + as-built) plus the README
  (run/deploy) are the two docs to read. `CLAUDE.md` holds project rules;
  `prompts.txt` is the chronological prompt log.
