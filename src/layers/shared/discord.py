import os

import requests
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


class Guild:
    @staticmethod
    def list_members(guild_id: int) -> list:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        params = {"limit": 1000}

        response = requests.get(
            f"https://discord.com/api/v10/guilds/{guild_id}/members",
            headers=headers,
            params=params,
        )

        response.raise_for_status()
        body = response.json()
        return body

    @staticmethod
    def get_member(guild_id: int, user_id: int) -> dict:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        response = requests.get(
            f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def set_nickname(guild_id: int, user_id: int, nickname: str | None) -> None:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        response = requests.patch(
            f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}",
            headers=headers,
            json={"nick": nickname},
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def add_role(guild_id: int, user_id: int, role_id: int) -> None:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        response = requests.put(
            f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
            headers=headers,
        )
        response.raise_for_status()
        return

    @staticmethod
    def remove_role(guild_id: int, user_id: int, role_id: int) -> None:
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        response = requests.delete(
            f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
            headers=headers,
        )
        response.raise_for_status()
        return


class Interaction:
    @staticmethod
    def create_message(
        interaction_id: str,
        interaction_token: str,
        components: list[dict] | None,
        type: int = 4,
        ephemeral: bool = False,
    ):
        response = requests.post(
            url=f"https://discord.com/api/v10/interactions/{interaction_id}/{interaction_token}/callback",
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            },
            json={
                "type": type,
                "data": {
                    "flags": FLAG_COMPONENTS_V2 | (FLAG_EPHEMERAL if ephemeral else 0),
                    "components": components or [],
                },
            },
        )
        response.raise_for_status()
        return

    @staticmethod
    def edit_original_message(
        interaction_token: str,
        components: list[dict] | None = None,
    ):
        response = requests.patch(
            f"https://discord.com/api/v10/webhooks/{APP_ID}/{interaction_token}/messages/@original",
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
            },
            json={
                "flags": FLAG_COMPONENTS_V2,
                "components": components,
            },
        )
        response.raise_for_status()
        return
