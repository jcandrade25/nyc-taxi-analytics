"""One-off helper: export the dashboard gold marts from dev.duckdb to
committed parquet files in app/data/ so the Streamlit Cloud deploy can read
them without running dbt. Re-run after rebuilding the warehouse."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "app" / "data"
OUT.mkdir(parents=True, exist_ok=True)

MARTS = [
    "fct_trips_by_time",
    "fct_revenue_by_pickup_zone",
    "fct_payment_type_behavior",
    "fct_tip_rate_by_time",
]

con = duckdb.connect(str(ROOT / "dev.duckdb"), read_only=True)
for m in MARTS:
    n = con.execute(f"select count(*) from main_marts.{m}").fetchone()[0]
    target = (OUT / f"{m}.parquet").as_posix()
    con.execute(f"copy (select * from main_marts.{m}) to '{target}' (format parquet)")
    print(f"{m}: {n} rows -> {target}")
con.close()
