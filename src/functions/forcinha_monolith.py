import json
import os

import httpx
from nacl.signing import VerifyKey

PUBLIC_KEY = os.environ.get("PUBLIC_KEY", None)
USER_AGENT = os.environ.get("USER_AGENT", None)

CLIENT_ID = os.environ.get("CLIENT_ID", None)
SSO_CALLBACK_URL = os.environ.get("CALLBACK_URL", None)

commands = [
    {
        "name": "vincular",
        "content": "Vincule sua conta do EVE-Online ao Discord",
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "label": "Log in with EVE Online",
                        "url": "",
                    }
                ],
            }
        ],
    }
]


def lambda_handler(event, context):
    if PUBLIC_KEY is None or USER_AGENT is None or CLIENT_ID is None:
        return {"statusCode": 500, "body": "Internal Server Error"}

    method = event.get("requestContext", {}).get("http", {}).get("method", "")

    if method != "POST":
        return {"statusCode": 405, "body": "Method Not Allowed"}

    if not verify_signature(event):
        return {"statusCode": 401, "body": "Unauthorized"}

    body = json.loads(event.get("body", "{}"))
    interaction_type = body.get("type", 0)

    if interaction_type == 1:  # PING
        return process_ping()

    if interaction_type == 2:  # Command
        return process_command(body)

    return {
        "statusCode": 400,
        "body": "Bad Request",
    }


def verify_signature(event: dict):
    signature = event.get("headers", {}).get("x-signature-ed25519", "")
    timestamp = event.get("headers", {}).get("x-signature-timestamp", "")
    body = event.get("body", "")

    try:
        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except:
        return False


def process_ping():
    return {
        "statusCode": 200,
        "headers": {"User-Agent": USER_AGENT, "Content-Type": "application/json"},
        "body": json.dumps({"type": 1}),
    }


def process_command(body: dict):
    interaction_id = body["id"]
    interaction_token = body["token"]
    command_name = body["data"]["name"]

    callback_url = f"https://discord.com/api/v10/interactions/{interaction_id}/{interaction_token}/callback"

    if command_name == "vincular":
        link_account(callback_url)
        return {"statusCode": 202}

    return {"statusCode": 400, "body": "Bad Request"}


def link_account(callback_url: str):
    state_token = "dummy"  # TODO implement
    eve_auth_url = f"https://login.eveonline.com/v2/oauth/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={SSO_CALLBACK_URL}&scope=publicData&state={state_token}"

    content = f"Clique no botão abaixo para vincular sua conta:"
    components = [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": "Log in with EVE Online",
                    "url": eve_auth_url,
                }
            ],
        }
    ]

    send_message(callback_url, content, components)
    return


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
