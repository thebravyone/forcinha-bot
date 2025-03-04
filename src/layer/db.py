import os
from datetime import datetime, timedelta, timezone

import boto3
from nanoid import generate

AWS_REGION = os.environ.get("AWS_REGION", "")

db = boto3.resource("dynamodb", region_name=AWS_REGION)

state_token_table = db.Table("forcinha_state-token")
user_table = db.Table("forcinha_user")


class state_token:
    @staticmethod
    def add(discord_user_id: str) -> str:
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

    @staticmethod
    def get(token: str) -> dict:
        response = state_token_table.get_item(Key={"state_token": token})
        return response.get("Item", None)


class user:
    @staticmethod
    def add(discord_user_id: str, character_id: str):
        user_table.put_item(
            Item={
                "discord_user_id": discord_user_id,
                "eve_character_id": character_id,
            }
        )
        return

    @staticmethod
    def get(discord_user_id: str):
        response = user_table.get_item(Key={"discord_user_id": discord_user_id})
        return response.get("Item", None)
