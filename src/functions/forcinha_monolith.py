import json
import os
import urllib.parse

import db
import httpx
from nacl.signing import VerifyKey

PUBLIC_KEY = os.environ.get("PUBLIC_KEY", None)
USER_AGENT = os.environ.get("USER_AGENT", None)

CLIENT_ID = os.environ.get("CLIENT_ID", None)
SSO_CALLBACK_URL = os.environ.get("CALLBACK_URL", None)


def lambda_handler(event, context):
    if PUBLIC_KEY is None or USER_AGENT is None or CLIENT_ID is None:
        return {"statusCode": 500, "body": "Internal Server Error"}

    method = event.get("requestContext", {}).get("http", {}).get("method", "")

    if method != "POST":
        return {"statusCode": 405, "body": "Method Not Allowed"}

    if not debug and not verify_signature(event):
        return {"statusCode": 401, "body": "Unauthorized"}

    body = json.loads(event.get("body", "{}"))
    interaction_type = body.get("type", 0)

    if interaction_type == 1:  # PING
        return process_ping()

    if interaction_type == 2:  # Command
        command_name = body["data"]["name"]
        if command_name == "vincular":
            return command_link_account(body)

    return {
        "statusCode": 400,
        "body": "Bad Request",
    }


def process_ping():
    return {
        "statusCode": 200,
        "headers": {"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        "body": json.dumps({"type": 1}),
    }


def command_link_account(command: dict):
    discord_user_id = command["user"]["id"]  # only works for DMs
    state_token = db.state_token.add(discord_user_id)

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

    content = f"Clique no botão abaixo para vincular sua conta do EVE Online e ter acesso aos canais internos."
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

    message_url = interaction_callback_url(command)
    send_message(message_url, content, components)

    return {"statusCode": 202}


def verify_signature(event: dict) -> bool:
    signature = event.get("headers", {}).get("x-signature-ed25519", "")
    timestamp = event.get("headers", {}).get("x-signature-timestamp", "")
    body = event.get("body", "")

    try:
        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except:
        return False


def debug(event: dict) -> bool:
    secret = event.get("headers", {}).get("x-debug-secret", "")
    debug_secret = os.environ.get("DEBUG_SECRET", None)

    if debug_secret is None:
        return False

    return secret == debug_secret


def interaction_callback_url(data: dict) -> str:
    return f"https://discord.com/api/v10/interactions/{data['id']}/{data['token']}/callback"


def send_message(url: str, content: str, components: dict = {}):
    httpx.post(
        url,
        headers={"User-Agent": USER_AGENT},
        json={
            "type": 4,
            "data": {"content": content, "components": components},
        },
    )
    return


if __name__ == "__main__":
    lambda_handler({}, None)
    pass
