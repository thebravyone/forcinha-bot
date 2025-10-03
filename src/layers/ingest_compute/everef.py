import json
import tarfile
from datetime import datetime, timedelta, timezone
from typing import Iterator

import fsspec
import polars as pl
import requests

BATCH_SIZE = 1_000
CORP_ID = 98028546  # FORCA

KILLMAIL_SCHEMA = pl.Schema(
    {
        "killmail_id": pl.UInt64,
        "date": pl.Date,
        "solar_system_id": pl.UInt32,
        "victim_character_id": pl.UInt32,
        "victim_corporation_id": pl.UInt32,
        "victim_alliance_id": pl.UInt32,
        "victim_ship_type_id": pl.UInt32,
        "attacker_character_id": pl.UInt32,
        "attacker_corporation_id": pl.UInt32,
        "attacker_alliance_id": pl.UInt32,
        "attacker_ship_type_id": pl.UInt32,
        "attacker_weapon_type_id": pl.UInt32,
        "attacker_damage_done": pl.UInt64,
        "total_attackers_count": pl.UInt16,
        "is_loss": pl.Boolean,
    }
)


class Killmail:
    @staticmethod
    def fetch_totals() -> dict:
        response = requests.get("https://data.everef.net/killmails/totals.json")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def fetch_killmails_from_date(date: datetime) -> pl.LazyFrame | None:
        filename = f"https://data.everef.net/killmails/{date.year}/killmails-{date.year}-{date.month:02d}-{date.day:02d}.tar.bz2"

        batch_data = []
        df_list = []

        with fsspec.open(filename, "rb") as file:
            with tarfile.open(fileobj=file, mode="r:bz2") as tar:
                for member in tar:
                    file = tar.extractfile(member)
                    if not file:
                        continue

                    file_data = json.loads(file.read())
                    batch_data.extend(Killmail._unpack_killmail(file_data))

                    if len(batch_data) >= BATCH_SIZE:
                        df_list.append(pl.DataFrame(batch_data, schema=KILLMAIL_SCHEMA))
                        batch_data.clear()

                if batch_data:  # parse leftovers
                    df_list.append(pl.DataFrame(batch_data, schema=KILLMAIL_SCHEMA))

        if df_list:
            return pl.concat(df_list).lazy()

        return None

    # generator to stream killmail data into flat structure
    @staticmethod
    def _unpack_killmail(killmail_data) -> Iterator[dict]:
        attackers = killmail_data["attackers"]

        base = {
            "killmail_id": killmail_data["killmail_id"],
            "date": datetime.strptime(
                killmail_data["killmail_time"], "%Y-%m-%dT%H:%M:%SZ"
            ).date(),
            "solar_system_id": killmail_data["solar_system_id"],
            "victim_character_id": killmail_data["victim"].get("character_id"),
            "victim_corporation_id": killmail_data["victim"].get("corporation_id"),
            "victim_alliance_id": killmail_data["victim"].get("alliance_id"),
            "victim_ship_type_id": killmail_data["victim"].get("ship_type_id"),
            "total_attackers_count": len(
                [attacker for attacker in attackers if attacker.get("character_id")]
            ),
            "is_loss": int(killmail_data["victim"].get("corporation_id")) == CORP_ID,
        }

        for attacker in attackers:
            if attacker.get("character_id") and (
                int(attacker.get("corporation_id")) == CORP_ID
                or int(killmail_data["victim"].get("corporation_id")) == CORP_ID
            ):
                yield {
                    **base,
                    "attacker_character_id": attacker["character_id"],
                    "attacker_corporation_id": attacker.get("corporation_id"),
                    "attacker_alliance_id": attacker.get("alliance_id"),
                    "attacker_ship_type_id": attacker.get("ship_type_id"),
                    "attacker_weapon_type_id": attacker.get("weapon_type_id"),
                    "attacker_damage_done": attacker.get("damage_done"),
                }
