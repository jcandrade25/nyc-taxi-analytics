# HANDOFF — Execution-Session Bridge

If you are the next agent (or human) picking up this project, **read
this file first**. It distills what's been decided, what's been done,
what's next, and what you must not re-debate.

If you only have time for one document: this one. If you have time
for two: this one and [PLAN.md](PLAN.md).

---

## Where we are right now

Scaffold-complete. **Zero models authored yet.** First commit pushed
to https://github.com/jcandrade25/nyc-taxi-analytics.

What exists:
- `dbt_project.yml`, `packages.yml` (git URLs, not hub), `profiles.yml.example` (gitignored at the real name), `requirements.txt`, `.gitignore`
- `models/staging/_sources.yml` — full TLC source definitions with column descriptions
- `PLAN.md` — architecture and decisions, the source of truth
- `CLAUDE.md` — project rules (prompt logging, conventions)
- `README.md` — public-facing entry point
- `docs/__overview.md`, `docs/caveats.md` — dbt doc blocks ready to be referenced
- `resources/` — raw parquet + zone CSV + TLC dictionary (committed for reviewer reproducibility)
- `prompts.txt` — chronological log of every prompt + response (CLAUDE.md rule)
- Empty directories with `.gitkeep`: `models/{staging,intermediate,marts}`, `seeds/`, `tests/`, `macros/`, `snapshots/`, `analyses/`

What does NOT exist yet:
- Any `.sql` model files
- Any seed CSVs (named in PLAN.md §8 but not yet created)
- `exposures.yml`
- The Streamlit app
- The dbt-docs site (`target/`)
- The `dev.duckdb` warehouse file

---

## Non-negotiables — do not re-debate

Each of these was decided after a real exchange. Re-litigating them
costs time and produces worse outcomes than executing them.

| Decision | Where it was decided |
| --- | --- |
| DuckDB locally, Snowflake-compatible by construction | PLAN.md §1 |
| Sources via `read_parquet()` / `read_csv_auto()` in `_sources.yml` | _sources.yml |
| `dbt_utils` + `dbt_expectations` (git URLs, not hub) | packages.yml |
| Medallion: staging=views, intermediate=tables, marts=tables | PLAN.md §2 + dbt_project.yml |
| **`int_trips__enriched` is a `table`, NOT ephemeral.** Four marts consume it; ephemeral would inline the joins four times | PLAN.md §2 |
| **Silver is three models**: `int_trips__cleansed` → `int_trips__deduped` → `int_trips__enriched` | PLAN.md §2, §4 |
| **`assert_store_and_fwd_dedupe.sql` runs against `__cleansed`**, NOT `__deduped`. The test must catch collisions in the population that arrives; running it against the deduped model would trivially pass | PLAN.md §3, §4 |
| **Monetary columns: `DECIMAL(10,2)` at row grain, explicit `DECIMAL(18,2)` cast on mart aggregates.** Sums across 11M rows exceed (10,2) | PLAN.md §2 |
| **`tip_pct_of_fare` denominator uses `NULLIF(fare_amount_usd, 0)`** | PLAN.md §9 |
| **Timestamps stay in NYC local time. No UTC conversion anywhere.** TLC convention; UTC would silently shift the heatmap | PLAN.md §6 |
| Single `fct_trips_by_time` mart at hour grain carries `pickup_date`, `pickup_hour`, `iso_week`, `day_of_week`, `is_weekend` — Streamlit picks `GROUP BY` at query time | PLAN.md §2 |
| Viz #4 is the **credit-card-only tip-rate heatmap** (`fct_tip_rate_by_time`), grain `(day_of_week, hour_of_day)`, carrying `trip_count` for confidence weighting | PLAN.md §2 |
| Cash-tip caveat surfaces in three places: doc block, column descriptions referencing it, and the dashboard chart subtitle | PLAN.md §5, docs/caveats.md |
| Surrogate key = `dbt_utils.generate_surrogate_key(['vendor_id', 'pickup_datetime', 'dropoff_datetime', 'pickup_location_id', 'dropoff_location_id'])` | PLAN.md §4 |
| Seeds: `payment_types.csv` and `rate_codes.csv` — NOT inlined CTEs | PLAN.md §8 |
| `profiles.yml` is gitignored; `profiles.yml.example` is committed | PLAN.md §8 |
| Streamlit query functions are all `@st.cache_data`-decorated | PLAN.md §6 |
| Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`) | CLAUDE.md |

---

## Things the sandbox can't do — work on the user's machine

The development sandbox can't reach `hub.getdbt.com` or
`extensions.duckdb.org` (proxy 403). On the user's machine these work
fine. Steps that need the real network:

- `dbt deps` — installs `dbt_utils`, `dbt_expectations`, and the
  transitive `dbt_date` from their GitHub URLs
- DuckDB `httpfs` / `parquet` extension auto-install (only matters if
  we later swap `parquet_glob` to an `s3://` URL)
- `dbt build` end-to-end (needs `dbt deps` to have completed first)

If you're running in the sandbox and need to verify model output, you
can hand off `dbt build` to the user as the verification step.

---

## Next prompt — start here

PLAN.md §9 has the full execution order. The next prompt is **step 1
+ 2**: seeds and bronze. Suggested verbatim:

> Build the seeds and the bronze layer. (1) Create
> `seeds/payment_types.csv` (TLC payment-type codes 0–6 with their
> labels) and `seeds/rate_codes.csv` (RatecodeID 1–6 plus 99 with
> labels). Add corresponding `seeds/_seeds.yml` with descriptions and
> primary-key tests. (2) Create the bronze staging models:
> `stg_tlc__trips`, `stg_tlc__zones`, `stg_tlc__payment_types`,
> `stg_tlc__rate_codes`. snake_case the columns, cast monetary fields
> to `DECIMAL(10,2)`, cast timestamps to `TIMESTAMP` (keep them NYC
> local), no row drops, no joins, no business logic. Add
> `models/staging/_models.yml` with model + column descriptions and
> the generic tests from PLAN.md §3 (accepted_values on
> `vendor_id` 1/2/6/7, `payment_type` 0..6, `rate_code_id` 1..6 + 99,
> `store_and_fwd_flag` Y/N; `expect_column_values_to_be_between` on
> `pickup_datetime` / `dropoff_datetime` for
> [2026-01-01, 2026-04-01); not_null + unique on the zone PK).

After that prompt, the order is:

3. **Silver**: `int_trips__cleansed` (no dedupe) →
   `int_trips__deduped` (row_number tiebreak) →
   `int_trips__enriched` (joins + derived columns).
4. **Gold dims**: `dim_zone`, `dim_date`.
5. **Gold facts**: `fct_trips` first, then `fct_trips_by_time`,
   `fct_revenue_by_pickup_zone`, `fct_payment_type_behavior`,
   `fct_tip_rate_by_time`.
6. **Singular tests** in `tests/`.
7. **Exposures + docs wiring**: `models/exposures.yml`, model/column
   description audit, `dbt docs generate`, screenshot the lineage
   graph.
8. **Streamlit app** at `app/streamlit_app.py`.
9. **README polish + Loom prep** (per PLAN.md §10).

---

## The per-prompt ritual

After **every** model-authoring prompt:

```bash
dbt parse                                    # syntax / refs valid?
dbt build --select <new_model>+              # build and test downstream
dbt build --select <new_model>+ --fail-fast  # if mid-debug
```

Before committing:

```bash
git status                                   # nothing in target/ or dbt_packages/?
dbt build                                    # full project still green?
```

Commit message format (CLAUDE.md):

```
feat(staging): add stg_tlc__trips with typed casts and not-null tests
fix(silver): NULLIF(fare_amount_usd, 0) in tip_pct denominator
chore(seeds): ship payment_types and rate_codes lookup CSVs
docs: add cash-tip caveat doc block
```

Then push to `main` (the assessment requires the repo be public; no
PR workflow needed for a 2–3 hour build).

---

## Gotchas in one place

- **DECIMAL precision.** Row-level `DECIMAL(10,2)`; mart aggregates
  explicitly `CAST(... AS DECIMAL(18,2))`. Engines auto-widen `SUM`
  but the explicit cast documents intent and prevents downstream
  truncation. See PLAN.md §2.
- **`tip_pct_of_fare` divide-by-zero.** Always wrap the denominator
  in `NULLIF(fare_amount_usd, 0)`. `payment_type = 3` (no charge)
  legitimately produces $0 fares.
- **Cash tips are invisible.** `tip_amount` is only populated for
  `payment_type = 1` (credit card). Cash tips show as `0.00` — not
  zero in reality, just unobserved. Any tip aggregation must filter
  to credit card OR carry a caveat. The `caveat__cash_tip_invisibility`
  doc block is the canonical wording.
- **`store_and_fwd_flag = 'Y'` and duplicates.** Vendor timestamp
  jitter on retransmits can defeat the surrogate key. We keep the
  duplicates in `__cleansed` so the test catches them, then dedupe
  in `__deduped` via `row_number() over (partition by
  trip_surrogate_id order by filename desc, pickup_datetime asc)`.
  Marts read from `__deduped`. **Do not dedupe in `__cleansed`** —
  that would defeat the test.
- **NYC local time everywhere.** No UTC conversion. `pickup_hour`,
  `day_of_week`, etc. are local-NYC. The heatmap depends on this.
- **Stray out-of-month rows.** TLC monthly files include occasional
  rows from neighboring months (typos, late records, clock skew).
  The `expect_column_values_to_be_between` test on
  `pickup_datetime` for `[2026-01-01, 2026-04-01)` catches them.
  When it fires, **don't suppress it** — investigate and either
  filter in `__cleansed` or widen the range deliberately.
- **`Airport_fee` casing.** The parquet schema has mixed case
  (`Airport_fee`, not `airport_fee`). Bronze must rename it.
- **`cbd_congestion_fee`.** Manhattan CBD congestion-pricing fee,
  added 2025. Lives in the `total_amount` already — don't double-count.
- **packages.yml uses git URLs**, not the hub. Sandbox-side
  reason was network restrictions, but it stays this way because
  it removes a single point of failure on `hub.getdbt.com`. Don't
  switch back unless asked.

---

## Files to read first (in order)

1. **HANDOFF.md** (you're here)
2. **PLAN.md** — every architectural decision with reasoning
3. **CLAUDE.md** — prompt-logging rule and conventions
4. **models/staging/_sources.yml** — the exact TLC source schema with
   column-level descriptions you'll mirror into bronze models
5. **dbt_project.yml** + **profiles.yml.example** — config you'll
   reference (`var()` calls, materialization defaults, profile shape)
6. **resources/Technical AI Assessment — Data.txt** — the original
   assessment brief, for grading-criteria sanity checks

---

## Definitions (project glossary)

- **Bronze / staging** — typed views over raw sources. One model per
  source table. No joins, no filters, no business logic.
- **Silver / intermediate** — cleansed and enriched. Three models:
  cleansed (filters + flagging, NO dedupe), deduped (row_number
  tiebreak), enriched (joins zones + payment-type + rate-code labels
  + derived columns).
- **Gold / marts** — pre-aggregated facts and dims at the exact grain
  one dashboard chart needs. One mart per chart. Aggregates
  `CAST(... AS DECIMAL(18,2))`.
- **Surrogate key** — `dbt_utils.generate_surrogate_key` over the
  5-tuple in §4. Hashed to `trip_surrogate_id`.
- **DQ test** — anything that fails `dbt build` on bad data. Generic
  tests live in YAML next to the model; singular tests live in
  `tests/*.sql` and assert business invariants.
- **Exposure** — declarative downstream consumer in dbt. The
  Streamlit app is registered as one so the lineage graph terminates
  at the dashboard.
- **Doc block** — `{% docs name %}…{% enddocs %}` markdown in
  `docs/*.md`. Referenced from `description: "{{ doc('name') }}"` so
  the prose lives in one file and appears verbatim everywhere it's
  cited.
- **Caveat** — a documented limitation of the data (cash-tip
  invisibility, store_and_fwd duplicates). Caveats live in doc
  blocks and propagate to every column or model affected.
