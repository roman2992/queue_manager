import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, to_timestamp


JDBC_URL = os.getenv(
    "JDBC_URL",
    "jdbc:postgresql://target-postgres:5432/queue_manager_replica",
)
DB_USER = os.getenv("DB_USER", "replica_user")
DB_PASSWORD = os.environ["DB_PASSWORD"]

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://seaweedfs:8333")
S3_BUCKET = os.getenv("S3_BUCKET", "queue-lake")
S3_PREFIX = os.getenv("S3_PREFIX", "bronze/queue_tickets")

CHECKPOINT_FILE = Path(
    os.getenv("CHECKPOINT_FILE", "/checkpoints/queue_tickets.json")
)

LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "5"))

ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "localaccesskey")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "localsecretkey123")


def read_checkpoint():
    if not CHECKPOINT_FILE.exists():
        return None

    with CHECKPOINT_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("watermark")


def write_checkpoint(watermark):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = CHECKPOINT_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as file:
        json.dump({"watermark": watermark}, file)

    temp_file.replace(CHECKPOINT_FILE)


def main():
    spark = (
        SparkSession.builder
        .appName("queue-tickets-incremental-ingest")
        .config(
            "spark.jars.packages",
            "org.postgresql:postgresql:42.7.5,"
            "org.apache.hadoop:hadoop-aws:3.3.4",
        )
        .config(
            "spark.hadoop.fs.s3a.endpoint",
            S3_ENDPOINT,
        )
        .config("spark.hadoop.fs.s3a.access.key", ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", SECRET_KEY)
        .config(
            "spark.hadoop.fs.s3a.path.style.access",
            "true",
        )
        .config(
            "spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        .config(
            "spark.hadoop.fs.s3a.connection.ssl.enabled",
            "false",
        )
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    try:
        # Capture a source-side upper bound so rows changing during this
        # run are picked up by this or the next run.
        bound_df = (
            spark.read.format("jdbc")
            .option("url", JDBC_URL)
            .option("driver", "org.postgresql.Driver")
            .option("dbtable", "(SELECT CURRENT_TIMESTAMP AS upper_bound) AS bounds")
            .option("user", DB_USER)
            .option("password", DB_PASSWORD)
            .load()
        )

        upper_bound = bound_df.first()["upper_bound"]

        previous = read_checkpoint()

        if previous:
            from datetime import timedelta

            lower_bound = (
                datetime.fromisoformat(previous.replace("Z", "+00:00"))
                - timedelta(minutes=LOOKBACK_MINUTES)
            )
            lower_sql = lower_bound.isoformat()
            print(f"Incremental lower bound: {lower_sql}", flush=True)
        else:
            lower_sql = None
            print("No checkpoint found; performing initial load.", flush=True)

        predicates = []
        if lower_sql:
            safe_lower = lower_sql.replace("'", "''")
            predicates.append(f"updated_at >= TIMESTAMPTZ '{safe_lower}'")

        upper_sql = upper_bound.isoformat()
        safe_upper = upper_sql.replace("'", "''")
        predicates.append(f"updated_at <= TIMESTAMPTZ '{safe_upper}'")

        where_clause = " AND ".join(predicates)
        query = (
            "(SELECT * FROM public.queue_tickets WHERE "
            + where_clause
            + ") AS source_rows"
        )

        df = (
            spark.read.format("jdbc")
            .option("url", JDBC_URL)
            .option("driver", "org.postgresql.Driver")
            .option("dbtable", query)
            .option("user", DB_USER)
            .option("password", DB_PASSWORD)
            .option("fetchsize", "1000")
            .load()
        )

        row_count = df.count()
        print(f"Rows selected: {row_count}", flush=True)

        if row_count:
            batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            output_path = f"s3a://{S3_BUCKET}/{S3_PREFIX}/batch_id={batch_id}"

            (
                df.write
                .mode("errorifexists")
                .parquet(output_path)
            )

            print(f"Parquet written to: {output_path}", flush=True)
        else:
            print("No rows in this interval; no Parquet written.", flush=True)

        # Advance only after the read/write path succeeded.
        write_checkpoint(upper_sql)
        print(f"Checkpoint advanced to {upper_sql}", flush=True)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
