{% docs caveat__cash_tip_invisibility %}

**Tips are observed only when the payment rail captures them
digitally.** Tip observability is a property of *how* the fare was
settled, not of the individual trip:

- **Observed** — credit card (`payment_type = 1`) and app-hailed
  **Flex Fare** (`payment_type = 0`). Both record the tip digitally,
  *including* genuine `0.00` tips (a rider who chose not to tip).
- **Unobserved** — cash (`2`) is never metered: a cash tip shows as
  `0.00` but the meter simply never saw it. No-charge (`3`),
  dispute (`4`), unknown (`5`), and voided (`6`) are non-standard
  settlements where a tip is not meaningfully recorded.

The `is_cash_tip_unobservable` flag encodes exactly this:
`payment_type in (2, 3, 4, 5, 6)`.

**Why Flex Fare is observed, not excluded.** Flex Fare is ~28% of the
dataset and ~266k of those trips carry real, digitally-captured tips.
An earlier version of this pipeline treated everything except credit
card as unobservable and the heatmap filtered to `payment_type = 1`,
silently discarding a quarter-million legitimate observations. Flex
Fare's genuine tip rate (~9%, far below credit card's ~90%) is
*signal* about app-hailed rider behavior, not noise to be hidden.

**Implications for analysis:**

- Any tip aggregation that includes **cash** (or no-charge / dispute /
  unknown / voided) systematically understates true tipping.
- A tip *rate* must include observed zero tips. Conditioning on
  `tip_amount > 0` (e.g. "include any row that has a tip") measures
  tip size *among tippers*, not the tip rate, and biases the average
  upward — so we partition by payment rail, not by whether a tip
  occurred.
- The tip-rate heatmap (`fct_tip_rate_by_time`) is built over the
  observed population (`not is_cash_tip_unobservable`) and carries a
  credit-card-only slice so the dashboard can toggle between the two.
- Average tip percent computed naively across *all* payment types
  still falls as the cash share rises, even if behavior is constant.

This is a property of the upstream source, not a pipeline bug. The
honest response is to scope tip analysis to the observed population
and disclose it — which is what this doc block exists to do.

{% enddocs %}


{% docs caveat__store_and_fwd_dedupe %}

**`store_and_fwd_flag = 'Y'` rows can produce duplicates.** This flag
means the trip record was held in vehicle memory because the device
had no connection to the vendor's server, then transmitted when
connectivity returned. Some vendors re-stamp the timestamps with
millisecond-level jitter on retransmit, which defeats the surrogate
key (`hash(vendor_id, pickup_datetime, dropoff_datetime,
pickup_location_id, dropoff_location_id)`).

**How the pipeline handles it:**

1. `int_trips__cleansed` does **not** dedupe. It preserves the
   collisions so the `assert_store_and_fwd_dedupe.sql` singular test
   can detect and count them.
2. `int_trips__deduped` runs
   `row_number() over (partition by trip_surrogate_id order by
   filename desc, pickup_datetime asc)` and keeps `rn = 1`. The
   tiebreak picks the latest-arriving file first (the retransmit
   usually wins), then the earliest pickup within that file.
3. All gold marts read from `__deduped`, so dashboard numbers are
   not inflated.
4. The dedupe test continues to fire when collisions occur — it's
   wired as a monitoring signal, not a hard gate. We don't suppress
   it; we observe it.

If you see this test failing with a small count (handful to a few
hundred), that's expected. If the count spikes, investigate the
upstream parquet drop — it may indicate a vendor schema change or a
larger connectivity incident.

{% enddocs %}
