import asyncio
import json
import os
import urllib
from datetime import datetime

import db
import httpx
import stamina

GUILD_ID = os.environ.get("GUILD_ID", None)
BOT_TOKEN = os.environ.get("BOT_TOKEN", None)

CLIENT_ID = os.environ.get("CLIENT_ID", None)
SSO_CALLBACK_URL = os.environ.get("CALLBACK_URL", None)

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

    discord_members = get_discord_members()  # Fetch all server members
    registered_members = get_registered_members()  # Fetch registered users

    audit_targets = [
        {
            "discord_user_id": user["user"]["id"],
            "discord_user_name": get_discord_member_name(user),
            "character_id": registered_members.get(user["user"]["id"], {}).get(
                "character_id", None
            ),
            "current_roles": set(
                int(role_id)
                for role_id in user["roles"]
                if int(role_id) in ROLES.values()
            ),
        }
        for user in discord_members
        if not user["user"].get("bot", False)
    ]

    dm_targets = [
        {
            "discord_user_id": user["user"]["id"],
            "discord_user_name": get_discord_member_name(user),
            "joined_at": datetime.fromisoformat(user["joined_at"]),
        }
        for user in discord_members
        if user["user"]["id"] not in registered_members
        and not user["user"].get("bot", False)
    ]

    audit_results = audit_and_fix_roles(audit_targets)
    dm_results = dm_unregistered_users(dm_targets)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "audited_count": len(audit_targets),
                "roles_added": audit_results["roles_added"],
                "roles_removed": audit_results["roles_removed"],
                "dm_sent": dm_results,
            }
        ),
    }


def audit_and_fix_roles(audit_targets: dict):
    # Fetch public data in bulk
    eve_public_data = get_batch_public_data(
        [user["character_id"] for user in audit_targets if user["character_id"]]
    )

    # Convert eve_public_data into a dictionary for O(1) lookup by Character ID
    public_data_map = {data["character_id"]: data for data in eve_public_data}

    # Create enriched registered users list
    audited_users = []
    for user in audit_targets:
        public_data = public_data_map.get(user["character_id"], {})
        audited_users.append(
            {
                "discord_user_id": user["discord_user_id"],
                "discord_user_name": user["discord_user_name"],
                "character_id": user.get("character_id", None),
                "corporation_id": public_data.get("corporation_id", None),
                "alliance_id": public_data.get("alliance_id", None),
                "current_roles": user["current_roles"],
                "target_roles": set(),
            }
        )

    # Determine target roles
    for user in audited_users:
        if user["corporation_id"] == CORP_ID:
            user["target_roles"].add(ROLES["Membro"])
        elif user["alliance_id"] in FRIENDLY_ALLIANCES_IDS:
            user["target_roles"].add(ROLES["Aliado"])

    roles_added, roles_removed = [], []
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}

    # Process role updates
    for user in audited_users:
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
                f"Role '{get_key_from_value(ROLES, role_id)}' adicionada a '{user['discord_user_name']}'"
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
                f"Role '{get_key_from_value(ROLES, role_id)}' removida de '{user['discord_user_name']}'"
            )

    return {
        "roles_added": roles_added,
        "roles_removed": roles_removed,
    }


def dm_unregistered_users(dm_targets: list):
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

    # DM only the 5 most recent members without registration
    dm_targets.sort(key=lambda x: x["joined_at"], reverse=True)
    dm_targets = dm_targets[:5]

    dm_sent = []
    for user in dm_targets:
        response = httpx.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers=headers,
            json={"recipient_id": user["discord_user_id"]},
        )

        response.raise_for_status()
        channel_id = response.json()["id"]

        state_token = db.state_token.add(user["discord_user_id"])
        query_string = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": SSO_CALLBACK_URL,
                "scope": "publicData",
                "state": state_token,
            }
        )

        auth_url = f"https://login.eveonline.com/v2/oauth/authorize?{query_string}"

        content = f"🍻 Seja bem-vindo ao discord das Forças Armadas!\n\nClique no botão abaixo para vincular sua conta do EVE Online e ter acesso aos canais internos."
        components = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "Log in with EVE Online",
                        "url": auth_url,
                    }
                ],
            }
        ]

        response = httpx.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            json={
                "content": content,
                "components": components,
            },
        )

        response.raise_for_status()
        db.users.add(discord_user_id=user["discord_user_id"])
        dm_sent.append(
            f"DM enviada para '{user["discord_user_name"]}' com instruções de registro"
        )

    return dm_sent


def get_discord_members() -> list:
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


def get_discord_member_name(member: dict):
    if member.get("nick"):
        return member["nick"]
    return member["user"]["global_name"]


def get_registered_members() -> list:
    return db.users.get_all()


def get_batch_public_data(character_ids: list[int]) -> list:
    async def fetch_character_data():
        semaphore = asyncio.Semaphore(25)  # Limit to 25 concurrent requests

        @stamina.retry(on=_is_retriable_error, attempts=3)
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
