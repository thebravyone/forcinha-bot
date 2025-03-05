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
SSO_CALLBACK_URL = os.environ.get("SSO_CALLBACK_URL", None)

CORP_ID = 98028546
FRIENDLY_ALLIANCES_IDS = [
    99003214,  # Brave Collective
    99010079,  # Brave United
    1354830081,  # Goonswarm Federation
]

ROLES = {
    "Membro": 1063973360914145290,
    "Aliado": 1122778799839391895,
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
            "discord_nick_name": user["nick"],
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

    # Fetch public data in bulk
    eve_public_data = get_batch_char_public_data(
        [user["character_id"] for user in audit_targets if user["character_id"]]
    )

    auditees = []
    for user in audit_targets:
        public_data = eve_public_data.get(user["character_id"], {})
        auditees.append(
            {
                "discord_user_id": user["discord_user_id"],
                "discord_user_name": user["discord_user_name"],
                "discord_nick_name": user["discord_nick_name"],
                "character_id": user.get("character_id", None),
                "character_name": public_data.get("name", None),
                "corporation_id": public_data.get("corporation_id", None),
                "alliance_id": public_data.get("alliance_id", None),
                "current_roles": user["current_roles"],
                "target_roles": set(),
            }
        )

    # audit nicknames
    nick_audit_results = audit_nicknames(auditees)
    auditees = nick_audit_results["auditees"]

    # audit roles and registration
    role_audit_results = audit_and_fix_roles(auditees)
    dm_results = dm_unregistered_users(dm_targets)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "audited_count": len(audit_targets),
                "nicks_updated": nick_audit_results["nicks_updated"],
                "roles_added": role_audit_results["roles_added"],
                "roles_removed": role_audit_results["roles_removed"],
                "dm_sent": dm_results,
            }
        ),
    }


def audit_and_fix_roles(audit_targets: dict):
    # Determine target roles
    for user in audit_targets:
        if user["corporation_id"] == CORP_ID:
            user["target_roles"].add(ROLES["Membro"])
        elif user["alliance_id"] in FRIENDLY_ALLIANCES_IDS:
            user["target_roles"].add(ROLES["Aliado"])

    roles_added, roles_removed = [], []
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}

    # Process role updates
    for user in audit_targets:
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


def audit_nicknames(audit_targets: dict):
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

    corporation_ids = set()
    for user in audit_targets:
        corporation_ids.add(user["corporation_id"])

    corporation_data = get_batch_corp_public_data(list(corporation_ids))

    nicks_updated = []
    for user in audit_targets:
        corporation_id = user["corporation_id"]
        corporation_ticker = corporation_data.get(corporation_id, {}).get(
            "ticker", None
        )

        target_nickname = None

        if user["character_name"]:
            target_nickname = user["character_name"]

        if corporation_ticker and corporation_id != CORP_ID:
            target_nickname = f"[{corporation_ticker}] {user['character_name']}"

        if target_nickname != user["discord_nick_name"]:
            try:
                response = httpx.patch(
                    f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{user['discord_user_id']}",
                    headers=headers,
                    json={"nick": target_nickname},
                )
                response.raise_for_status()
                nicks_updated.append(
                    f"Nickname de '{user['discord_user_name']}' atualizado para '{target_nickname}'"
                )
                if target_nickname is not None:
                    user["discord_user_name"] = target_nickname
            except:
                nicks_updated.append(
                    f"Falha ao atualizar o nickname de '{user['discord_user_name']}'"
                )

    return {
        "auditees": audit_targets,
        "nicks_updated": nicks_updated,
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

        try:
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                db.users.add(discord_user_id=user["discord_user_id"])
                dm_sent.append(
                    f"Falha ao enviar DM para '{user["discord_user_name"]}' (Permissão negada)"
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


def get_batch_char_public_data(character_ids: list[int]) -> list:
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
    return {data["character_id"]: data for data in public_data}


def get_batch_corp_public_data(corporation_ids: list[int]) -> list:
    async def fetch_corporation_data():
        semaphore = asyncio.Semaphore(25)  # Limit to 25 concurrent requests

        @stamina.retry(on=_is_retriable_error, attempts=3)
        async def fetch(corporation_id):
            async with semaphore:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"https://esi.evetech.net/latest/corporations/{corporation_id}/",
                        timeout=10,
                    )
                    response.raise_for_status()
                    return {"corporation_id": corporation_id, **response.json()}

        tasks = [
            fetch(corporation_id)
            for corporation_id in corporation_ids
            if corporation_id is not None
        ]
        responses = await asyncio.gather(*tasks)
        return responses

    corporation_data = asyncio.run(fetch_corporation_data())
    return {data["corporation_id"]: data for data in corporation_data}


def get_key_from_value(dictionary, target_value):
    for key, value in dictionary.items():
        if value == target_value:
            return key
    return None


if __name__ == "__main__":
    print(lambda_handler({}, None))
    pass
