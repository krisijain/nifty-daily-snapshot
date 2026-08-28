import csv
import io
import os
from datetime import datetime, timezone
import yfinance as yf
from flask import Flask, jsonify
from google.cloud import bigquery


STOCKS = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFY": "INFY.NS",
}

PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
DATASET = os.environ.get("BQ_DATASET", "stock_data")
TABLE = os.environ.get("BQ_TABLE", "daily_prices")

FIELDS = ["trade_date", "symbol", "close_price", "volume", "fetched_at"]

SCHEMA = [
    bigquery.SchemaField("trade_date", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("close_price", "NUMERIC", mode="REQUIRED"),
    bigquery.SchemaField("volume", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("fetched_at", "TIMESTAMP", mode="REQUIRED"),
]

app = Flask(__name__)


def fetch_stock_data():
    #Fetching the latest closing price and volume for each stock
    records = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for symbol, ticker_symbol in STOCKS.items():
        print(f"Fetching data for {symbol}....")

        data = yf.Ticker(ticker_symbol).history(
            period="5d", interval="1d", auto_adjust=False
        )

        #Dropping incomplete rows
        data = data.dropna(subset=["Close", "Volume"])

        if data.empty:
            raise RuntimeError(f"No data returned for {symbol}")

        latest = data.iloc[-1]

        records.append(
            {
                "trade_date": data.index[-1].date().isoformat(),
                "symbol": symbol,
                "close_price": round(float(latest["Close"]), 2),
                "volume": int(latest["Volume"]),
                "fetched_at": fetched_at,
            }
        )

    return records


def create_csv(records):
    #Converting the records into CSV format that is suitable for BigQuery
    buffer = io.StringIO()

    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(records)

    buffer.seek(0)
    return io.BytesIO(buffer.getvalue().encode("utf-8"))


def load_to_bigquery(csv_file):
    #Loading the data from CSV into BigQuery
    if not PROJECT_ID:
        raise RuntimeError("GCP_PROJECT_ID is not set")

    client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET}.{TABLE}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=SCHEMA,

        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    job = client.load_table_from_file(csv_file, table_ref, job_config=job_config)
    job.result()

    print(f"Loaded {job.output_rows} rows into {table_ref}")
    return table_ref, job.output_rows


def run_pipeline():
    records = fetch_stock_data()
    table_ref, rows_loaded = load_to_bigquery(create_csv(records))
    return table_ref, rows_loaded


@app.route("/", methods=["GET", "POST"])
def snapshot():
    try:
        table_ref, rows_loaded = run_pipeline()
        return jsonify(
            {"status": "success", "table": table_ref, "rows_loaded": rows_loaded}
        ), 200
    except Exception as exc:
        app.logger.exception("Stock snapshot failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    if os.environ.get("RUN_ONCE") == "true":
        run_pipeline()
    else:
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))