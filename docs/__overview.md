{% docs __overview__ %}

# NYC Yellow Taxi Analytics

This is the dbt documentation site for the
[`nyc-taxi-analytics`](https://github.com/jcandrade25/nyc-taxi-analytics)
project — an analytics-engineering pipeline that turns raw NYC TLC
yellow-taxi trip records (Jan–Mar 2026, ~11M rows) into a small set of
trusted, business-facing facts powering a Streamlit dashboard.

## Architecture

The pipeline follows a medallion pattern:

- **Bronze** (`models/staging/`) — typed views over the raw parquet
  sources and the zone-lookup CSV. `snake_case` columns, explicit
  type casts (monetary fields → `DECIMAL(10,2)`), no row drops.
- **Silver** (`models/intermediate/`) — three tables: `cleansed`
  (data-quality filters, **no dedupe** so the dedupe singular test
  can catch surrogate-key collisions), `deduped` (`row_number()`
  picks one row per surrogate key), `enriched` (zone and lookup
  joins, derived columns like `trip_duration_minutes`,
  `average_speed_mph`, `tip_pct_of_fare`).
- **Gold** (`models/marts/`) — pre-aggregated facts and dims at the
  exact grain a single dashboard chart needs. Monetary aggregates
  explicitly cast to `DECIMAL(18,2)`.

## Time window

January 1, 2026 through March 31, 2026 (Q1 2026). 3,724,889 trips in
January, 3,399,866 in February, 3,952,451 in March.

## The four dashboard views

`fct_trips_by_time` (grain: pickup_hour) carries date / week /
day-of-week / weekend so Streamlit picks the GROUP BY at query time —
the Trip Volume Over Time chart can render day, week, and hour views
from a single mart. `fct_revenue_by_pickup_zone` (grain: pickup_zone)
powers the top-performing zones chart with total revenue, average
fare, and trip count. `fct_payment_type_behavior` (grain:
payment_type) drives the rider-behavior comparison across the seven
TLC payment codes. `fct_tip_rate_by_time` (grain: day_of_week ×
hour_of_day) is the credit-card-only tip-rate heatmap (see the
cash-tip caveat below).

## Data quality

Generic tests on every PK, FK, and bounded value
(`accepted_values`, `accepted_range`,
`expect_column_values_to_be_between`). Singular tests in `tests/` for
business invariants like "pickup before dropoff" and "no negative
revenue except refunds". `assert_store_and_fwd_dedupe.sql`
intentionally runs against the **cleansed** model, not the deduped
one, so it surfaces collisions in the population that arrives from
the source.

## Caveats

Two limitations every consumer must understand:

- **Cash-tip invisibility** — `tip_amount` is populated only for
  credit-card transactions; cash tips show as `0.00` and are
  unobserved. The `fct_tip_rate_by_time` mart filters to
  `payment_type = 1` for this reason.
- **`store_and_fwd_flag = 'Y'` duplicates** — vendor timestamp jitter
  on retransmits can defeat the trip surrogate key.
  `int_trips__cleansed` preserves the collisions so the dedupe test
  catches them; `int_trips__deduped` then picks one row per
  surrogate key for the marts to consume.

Both have full doc blocks (`caveat__cash_tip_invisibility`,
`caveat__store_and_fwd_dedupe`) referenced from every column or model
they materially affect — search this docs site for the doc-block name
to see the canonical wording and every reference site.

## Time zone

All timestamps are NYC local. **No UTC conversion anywhere.** This is
the TLC convention and matches how operators reason about the data;
UTC conversion would silently shift the heatmap.

## Where to go next

- **[Repository](https://github.com/jcandrade25/nyc-taxi-analytics)**
  for source code, PLAN.md (architecture and decisions), and the
  README quickstart.
- The **lineage graph** terminates at the
  `streamlit_taxi_dashboard` exposure — click any mart to see which
  dashboard chart consumes it.

{% enddocs %}
