"""
The Google Cloud version of load.py: load the landing files from a Cloud Storage bucket into BigQuery,
with the same raw table names, so the dbt models run unchanged on the `bq` target.

Not run in this version. Needs `pip install google-cloud-bigquery` and application-default credentials.

Usage:
    python -m warehouse.bq_load <project> <dataset> <bucket>
"""
import sys

JSONL_TABLES = {
    "scraped_prices": "raw/source=*/date=*/part-*.jsonl",
    "scrape_runs": "raw/source=_runs/date=*/*.jsonl",
}
CSV_TABLES = {"m5_sales_long": "raw/m5/m5_sales_long.csv", "m5_prices": "raw/m5/m5_prices.csv",
              "m5_calendar": "raw/m5/calendar.csv"}


def load_all_bigquery(project: str, dataset: str, bucket: str) -> dict[str, int]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    jsonl = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON, autodetect=True,
                                   write_disposition="WRITE_TRUNCATE")
    csv = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.CSV, autodetect=True, skip_leading_rows=1,
                                 write_disposition="WRITE_TRUNCATE")
    counts = {}
    for tables, config in ((JSONL_TABLES, jsonl), (CSV_TABLES, csv)):
        for table, pattern in tables.items():
            job = client.load_table_from_uri(f"gs://{bucket}/{pattern}", f"{project}.{dataset}.{table}", job_config=config)
            counts[table] = job.result().output_rows
    return counts


if __name__ == "__main__":
    print(load_all_bigquery(*sys.argv[1:4]))
