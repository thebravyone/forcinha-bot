import os
from datetime import datetime, timedelta, timezone

import boto3
import nanoid

AWS_REGION = os.environ["AWS_REGION"]
STATE_TOKEN_TABLE_NAME = os.environ["STATETOKENTABLE_TABLE_NAME"]
USERS_TABLE_NAME = os.environ["USERSTABLE_TABLE_NAME"]
EVEENTITIESMETADATA_TABLE_NAME = os.environ["EVEENTITIESMETADATA_TABLE_NAME"]


dynamo = boto3.resource("dynamodb", region_name=AWS_REGION)

state_token_table = dynamo.Table(STATE_TOKEN_TABLE_NAME)
users_table = dynamo.Table(USERS_TABLE_NAME)
entities_metadata_table = dynamo.Table(EVEENTITIESMETADATA_TABLE_NAME)


class StateToken:
    @staticmethod
    def add(discord_user_id, interaction_token) -> str:
        token = nanoid.generate(size=10)
        state_token_table.put_item(
            Item={
                "state_token": token,
                "discord_user_id": discord_user_id,
                "interaction_token": interaction_token,
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


class User:
    @staticmethod
    def upsert(discord_user_id, character_id=None) -> None:
        users_table.put_item(
            Item={
                "discord_user_id": str(discord_user_id),
                "character_id": character_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return

    @staticmethod
    def get_all() -> dict:
        response = users_table.scan()
        users = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = users_table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            users.extend(response.get("Items", []))

        return users


class EntityMetadata:
    """
    Caches metadata for EVE entities such as characters, corporations, and alliances.

    Only immutable data should be stored, such as names and tickers.
    """

    @staticmethod
    def get(id: int) -> dict:
        response = entities_metadata_table.get_item(Key={"id": str(id)})
        return response.get("Item", None)

    @staticmethod
    def upsert(id: int, data: dict) -> None:
        item = {
            "id": str(id),
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        entities_metadata_table.put_item(Item=item)
        return


# class users:
#     def get_all():
#         body = bucket.Object(f"users.json").get()["Body"].read()
#         return json.loads(body)

#     def get(discord_user_id):
#         user_data = users.get_all()
#         return user_data.get(str(discord_user_id), None)

#     def add(discord_user_id, character_id=None):
#         user_data = users.get_all()
#         user_data[str(discord_user_id)] = {
#             "character_id": character_id,
#             "updated_at": datetime.now().isoformat(),
#         }

#         bucket.Object(f"users.json").put(Body=json.dumps(user_data))
#         return
