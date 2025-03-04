import base64
import os

import db
import httpx

CLIENT_ID = os.environ.get("CLIENT_ID", None)
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", None)


def lambda_handler(event, context):

    if CLIENT_ID is None or CLIENT_SECRET is None:
        return {"statusCode": 500, "body": "Internal Server Error"}

    method = event.get("requestContext", {}).get("http", {}).get("method", "")

    if method != "GET":
        return {"statusCode": 405, "body": "Method Not Allowed"}

    query_params = event.get("queryStringParameters", {})

    authorization_code = query_params.get("code", None)
    state_token = query_params.get("state", None)

    if authorization_code is None or state_token is None:
        return {"statusCode": 400, "body": "Bad Request"}

    access_token = request_token(authorization_code)["access_token"]
    public_data = get_public_data(access_token)

    discord_user_id = db.state_token.get(state_token)["discord_user_id"]
    character_id = public_data["CharacterID"]

    db.users.add(discord_user_id, character_id)
    return {"statusCode": 200, "body": "OK"}


def request_token(authorization_code: str):
    basic_auth = base64.urlsafe_b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
    ).decode()

    headers = {
        "Authorization": f"Basic {basic_auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    payload = {
        "grant_type": "authorization_code",
        "code": authorization_code,
    }

    response = httpx.post(
        "https://login.eveonline.com/v2/oauth/token",
        headers=headers,
        data=payload,
    )

    response.raise_for_status()
    return response.json()


def get_public_data(access_token: str):
    url = "https://esi.evetech.net/verify/"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = httpx.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()
    return data


if __name__ == "__main__":
    response = lambda_handler(
        {
            "requestContext": {"http": {"method": "POST"}},
            "queryStringParameters": {
                "code": "cccoi5jvCEW_hadc564YOw",
                "state": "ZjzLpEHxHfAkq6LA",
            },
        },
        None,
    )
    print(response)
    pass
