import json
import os

import httpx
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

PUBLIC_KEY = os.environ.get("PUBLIC_KEY", None)
USER_AGENT = os.environ.get("USER_AGENT", None)


def lambda_handler(event, context):
    if PUBLIC_KEY is None or USER_AGENT is None:
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

    callback_url = f"https://discord.com/api/v10/interactions/{interaction_id}/{interaction_token}/callback"

    httpx.post(
        callback_url,
        headers={"User-Agent": USER_AGENT},
        json={
            "type": 4,
            "data": {
                "content": "Congrats on sending your command!",
            },
        },
    )

    return {"statusCode": 202}


if __name__ == "__main__":
    lambda_handler({}, None)
    pass
