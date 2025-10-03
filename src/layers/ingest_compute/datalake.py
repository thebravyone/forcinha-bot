import json
import os

import boto3
import polars as pl

s3_client = boto3.client("s3")

DATALAKE_BUCKET = os.environ["DATALAKE_BUCKET_NAME"]


class Killmail:

    @staticmethod
    def upsert(killmails: pl.LazyFrame) -> None:
        if killmails is None:
            return

        killmails.collect().write_parquet(
            f"s3://{DATALAKE_BUCKET}/killmails", partition_by=["date"]
        )
        return

    def get() -> pl.LazyFrame:
        return pl.scan_parquet(f"s3://{DATALAKE_BUCKET}/killmails/")

    @staticmethod
    def set_totals(totals: dict) -> None:
        s3_client.put_object(
            Bucket=DATALAKE_BUCKET,
            Key="killmail-totals.json",
            Body=json.dumps(totals),
        )
        return

    @staticmethod
    def get_totals() -> dict:
        try:
            response = s3_client.get_object(
                Bucket=DATALAKE_BUCKET,
                Key="killmail-totals.json",
            )
            content = response["Body"].read().decode("utf-8")
            return json.loads(content)
        except s3_client.exceptions.NoSuchKey:
            return {}
