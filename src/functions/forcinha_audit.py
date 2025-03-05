import asyncio
import os

import db
import httpx
import stamina

GUILD_ID = os.environ.get("GUILD_ID", None)
BOT_TOKEN = os.environ.get("BOT_TOKEN", None)

CORP_ID = 98028546
FRIENDLY_ALLIANCES_IDS = [
    99003214,  # Brave Collective
    99010079,  # Brave United
    1354830081,  # Goonswarm Federation
]

ROLES = {
    "Membro": 1346269819393282150,
    "Aliado": 1346584727850713200,
}


def _is_retriable_error(exc: Exception) -> bool:
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code >= 500
        or isinstance(exc, httpx.HTTPError)
        or isinstance(exc, httpx.ReadTimeout)
    )


def lambda_handler(event, context):
    if GUILD_ID is None or BOT_TOKEN is None:
        return {"statusCode": 500, "body": "Internal Server Error"}

    members = get_member_list()  # Fetch all server members
    registered_users = get_registered_users()  # Fetch registered users

    # Convert members to a dictionary for O(1) lookup by Discord user ID
    members_map = {member["user"]["id"]: member for member in members}

    # Filter registered users to only those who are in the Discord server
    registered_users = [
        user for user in registered_users if user["discord_user_id"] in members_map
    ]

    # Fetch public data in bulk
    character_ids = [
        user["character_id"] for user in registered_users if user["character_id"]
    ]
    eve_public_data = get_batch_public_data(character_ids)

    # Convert eve_public_data into a dictionary for O(1) lookup by Character ID
    public_data_map = {data["character_id"]: data for data in eve_public_data}

    # Create enriched registered users list
    composite_users = []
    for user in registered_users:
        public_data = public_data_map.get(user["character_id"])
        if not public_data:
            continue

        member = members_map[user["discord_user_id"]]
        composite_users.append(
            {
                "discord_user_id": user["discord_user_id"],
                "character_id": user["character_id"],
                "character_name": public_data["name"],
                "corporation_id": public_data["corporation_id"],
                "alliance_id": public_data["alliance_id"],
                "current_roles": set(
                    int(role_id) for role_id in member["roles"]
                ),  # Convert to set for fast operations
                "target_roles": set(),
            }
        )

    # Determine target roles
    for user in composite_users:
        if user["corporation_id"] == CORP_ID:
            user["target_roles"].add(ROLES["Membro"])
        elif user["alliance_id"] in FRIENDLY_ALLIANCES_IDS:
            user["target_roles"].add(ROLES["Aliado"])

    roles_added, roles_removed = [], []
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}

    # Process role updates
    for user in composite_users:
        discord_user_id = user["discord_user_id"]

        # Add missing roles
        roles_to_add = user["target_roles"] - user["current_roles"]
        for role_id in roles_to_add:
            response = httpx.put(
                f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{discord_user_id}/roles/{role_id}",
                headers=headers,
            )
            response.raise_for_status()
            roles_added.append(
                f"Role '{get_key_from_value(ROLES, role_id)}' adicionada a {user['character_name']}"
            )

        # Remove extra roles
        roles_to_remove = user["current_roles"] - user["target_roles"]
        for role_id in roles_to_remove:
            response = httpx.delete(
                f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{discord_user_id}/roles/{role_id}",
                headers=headers,
            )
            response.raise_for_status()
            roles_removed.append(
                f"Role '{get_key_from_value(ROLES, role_id)}' removida de {user['character_name']}"
            )

    # Identify users who are in the Discord but not registered
    registered_discord_ids = {user["discord_user_id"] for user in composite_users}
    all_discord_ids = set(members_map.keys())
    not_registered_user_ids = list(all_discord_ids - registered_discord_ids)

    return {
        "registered_users": composite_users,
        "roles_added": roles_added,
        "roles_removed": roles_removed,
        "not_registered_user_ids": not_registered_user_ids,
    }


def get_member_list() -> list:
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    params = {"limit": 1000}

    response = httpx.get(
        f"https://discord.com/api/v10/guilds/{GUILD_ID}/members",
        headers=headers,
        params=params,
    )

    response.raise_for_status()
    body = response.json()
    return body


def get_registered_users() -> list:
    raw_data = db.users.get_all()
    return [
        {
            "discord_user_id": discord_user_id,
            "character_id": raw_data[discord_user_id]["character_id"],
        }
        for discord_user_id in raw_data.keys()
    ]


@stamina.retry(on=_is_retriable_error, attempts=3)
def get_public_data(character_id: int) -> dict:
    response = httpx.get(
        f"https://esi.evetech.net/v5/characters/{character_id}/", timeout=10
    )
    response.raise_for_status()
    return response.json()


def get_batch_public_data(character_ids: list[int]) -> list:
    async def fetch_character_data():
        semaphore = asyncio.Semaphore(25)  # Limit to 25 concurrent requests

        async def fetch(character_id):
            async with semaphore:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://esi.evetech.net/latest/characters/{character_id}/",
                        timeout=10,
                    )
                    response.raise_for_status()
                    return {"character_id": character_id, **response.json()}

        tasks = [fetch(character_id) for character_id in character_ids]
        responses = await asyncio.gather(*tasks)
        return responses

    public_data = asyncio.run(fetch_character_data())
    return public_data


def get_key_from_value(dictionary, target_value):
    for key, value in dictionary.items():
        if value == target_value:
            return key
    return None


if __name__ == "__main__":
    print(lambda_handler({}, None))
    pass
