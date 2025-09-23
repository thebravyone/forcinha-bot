import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from nanoid import generate

AWS_REGION = os.environ.get("AWS_REGION", "")
FORCINHA_BUCKET = os.environ.get("FORCINHA_BUCKET", "")

dynamo_client = boto3.resource("dynamodb", region_name=AWS_REGION)
state_token_table = dynamo_client.Table("forcinha_state-token")

s3_client = boto3.resource("s3", region_name=AWS_REGION)
bucket = s3_client.Bucket(FORCINHA_BUCKET)


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


class users:
    def get_all():
        body = bucket.Object(f"users.json").get()["Body"].read()
        return json.loads(body)

    def get(discord_user_id):
        user_data = users.get_all()
        return user_data.get(str(discord_user_id), None)

    def add(discord_user_id, character_id=None):
        user_data = users.get_all()
        user_data[str(discord_user_id)] = {
            "character_id": character_id,
            "updated_at": datetime.now().isoformat(),
        }

        bucket.Object(f"users.json").put(Body=json.dumps(user_data))
        return
