import base64
import os

import db
import httpx

BOT_TOKEN = os.environ.get("BOT_TOKEN", None)

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
    send_confirmation_dm(discord_user_id)
    force_audit()

    return show_confirmation_page()


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


def force_audit():
    try:
        httpx.get(
            "https://r2zrcqmbzurqzwewqpeqsnfpoy0skysk.lambda-url.us-east-1.on.aws/",
            timeout=0.2,  # fire and forget
        )
    except:
        pass


def send_confirmation_dm(discord_user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    response = httpx.post(
        "https://discord.com/api/v10/users/@me/channels",
        headers=headers,
        json={"recipient_id": discord_user_id},
    )

    response.raise_for_status()
    channel_id = response.json()["id"]

    content = f"✅  Sua conta do EVE Online foi vinculada ao discord com sucesso!\n\nAgora cadastre-se na Aliança e na Coalizão utilizando os botões abaixo:"
    components = [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": "Brave Core Services",
                    "url": "https://account.bravecollective.com/",
                },
                {
                    "type": 2,
                    "style": 5,
                    "label": "Goonfleet.com",
                    "url": "https://gice.goonfleet.com/",
                },
            ],
        }
    ]

    try:
        httpx.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            json={
                "content": content,
                "components": components,
            },
            timeout=0.2,  # fire and forget
        )
    except:
        pass

    return


def show_confirmation_page():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ForcinhaBot</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                background-color: #1a1a1a;
                color: white;
                margin: 0;
            }
            .container {
                display: flex;
                align-items: center;
                gap: 36px;
            }
            .text {
                font-size: 18px;
            }
            .gif img {
                width: 320px;
                height: auto;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="gif">
                <img src="https://forcinha-bot-publico.s3.us-east-1.amazonaws.com/bender_shooting.gif" alt="PVP GIF">
            </div>
            <div class="text">
                <h1>#SUCESSO</h1>
                Você já pode fechar essa página ✅
            </div>
        </div>
    </body>
    </html>
    """

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": html_content,
    }


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
    pass
