import os
from datetime import datetime, timedelta, timezone

import boto3
from nanoid import generate

AWS_REGION = os.environ.get("AWS_REGION", "")

db = boto3.resource("dynamodb", region_name=AWS_REGION)

state_token_table = db.Table("forcinha_state-token")
user_table = db.Table("forcinha_user")


class state_token:
    def add(discord_user_id: int) -> str:
        token = generate(size=16)
        state_token_table.put_item(
            Item={
                "state_token": token,
                "discord_user_id": discord_user_id,
                "ttl": int(
                    (datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()
                ),
            }
        )
        return token

    def get(token: str) -> dict:
        response = state_token_table.get_item(Key={"state_token": token})
        return response.get("Item", None)


class user:
    def add(discord_user_id: str, character_id: str):
        user_table.put_item(
            Item={
                "discord_user_id": discord_user_id,
                "character_id": character_id,
            }
        )
        return

    def get(discord_user_id: str):
        response = user_table.get_item(Key={"discord_user_id": discord_user_id})
        return response.get("Item", None)

    def get_many(discord_user_ids: list[str]):
        keys = [{"discord_user_id": id} for id in discord_user_ids]

        keys_batch = [keys[i : i + 100] for i in range(0, len(keys), 100)]

        items = []
        for keys in keys_batch:
            response = user_table.batch_get_item(Keys=keys)
            items.extend(response.get("Items", []))

        response = user_table.batch_get_item(Keys=keys)
        return response.get("Items", None)
