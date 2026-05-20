# Project Rules
## Prompt Logging
Every time you receive a new instruction or prompt, append it to prompts.txt 
in the project root with a timestamp (ISO 8601) and a brief summary of what 
you did in response. Create the file if it doesn't exist.
## Project Context
This is an analytics engineering project for NYC yellow taxi trip data (Jan-Mar 2026).
Stack: dbt-duckdb (local dev, production would be Snowflake), Streamlit + Plotly for viz.
Architecture: medallion pattern — staging (bronze) → intermediate (silver) → marts (gold).
Data: 3 parquet files (~3M rows each) + taxi_zone_lookup.csv (265 zones).
## Conventions
- SQL: snake_case columns, explicit casting, CTEs over subqueries
- dbt: refs over hardcoded table names, generic tests in YAML, singular tests in tests/
- Models: staging = views, intermediate = ephemeral, marts = tables
- Git: conventional commits (feat:, fix:, chore:, docs:)
