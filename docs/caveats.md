{% docs caveat__cash_tip_invisibility %}

**Cash tips are not captured in this dataset.** Per the TLC data
dictionary, `tip_amount` is populated automatically only for
credit-card transactions (`payment_type = 1`). Cash tips appear in
the data as `0.00` — not because riders tipped zero, but because the
meter never observed the tip.

**Implications for analysis:**

- Any tip aggregation that includes non-credit-card trips
  systematically understates true tipping behavior.
- Cross-payment-type tip comparisons should treat cash-tip values as
  unobserved, not as zero.
- The tip-rate heatmap (`fct_tip_rate_by_time`) filters to
  `payment_type = 1` for this reason. The dashboard chart carries an
  in-chart caveat for the same reason.
- Average tip percent computed naively across all payment types will
  fall as the cash-share of trips rises, even if tipping behavior
  among credit-card users is constant.

This is a property of the upstream source, not a pipeline bug. There
is no fix without external data; the only honest response is
disclosure, which is what this doc block exists to do.

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
