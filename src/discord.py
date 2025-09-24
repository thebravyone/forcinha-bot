import os

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

USER_AGENT = "DiscordBot (https://github.com/thebravyone/forcinha-bot, 1.0.0)"

APP_ID = os.environ["APP_ID"]
PUBLIC_KEY = os.environ["PUBLIC_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

FLAG_COMPONENTS_V2 = 1 << 15
FLAG_EPHEMERAL = 1 << 6


def verify_signature(event: dict) -> bool:
    headers = event.get("headers", {})
    signature = headers.get("x-signature-ed25519", "")
    timestamp = headers.get("x-signature-timestamp", "")

    body = event.get("body", "")
    try:
        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False


def pong() -> dict:
    return {
        "statusCode": 200,
        "headers": {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        "body": '{"type":1}',
    }


def list_members(guild_id: int) -> list:
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    params = {"limit": 1000}

    response = httpx.get(
        f"https://discord.com/api/v10/guilds/{guild_id}/members",
        headers=headers,
        params=params,
    )

    response.raise_for_status()
    body = response.json()
    return body


def add_role(guild_id: int, user_id: int, role_id: int) -> None:
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    response = httpx.put(
        f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
        headers=headers,
    )
    response.raise_for_status()
    return


def remove_role(guild_id: int, user_id: int, role_id: int) -> None:
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    response = httpx.delete(
        f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
        headers=headers,
    )
    response.raise_for_status()
    return


def respond_interaction(original_command: dict, components: dict):
    response = httpx.post(
        url=f"https://discord.com/api/v10/interactions/{original_command['id']}/{original_command['token']}/callback",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
        json={
            "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
            "data": {
                "flags": FLAG_COMPONENTS_V2 | FLAG_EPHEMERAL,
                "components": components,
            },
        },
    )
    response.raise_for_status()
    return
