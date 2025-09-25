import json
import os

import boto3
import db
import discord
import eveonline
from aws_xray_sdk.core import patch_all

patch_all()

QUEUE_URL = os.environ["AUDITUSER_QUEUE_URL"]
sqs = boto3.client("sqs")


def handler(event, context):

    query_params = event.get("queryStringParameters", {})

    authorization_code = query_params.get("code", None)
    state = query_params.get("state", None)

    try:
        access_token = eveonline.Auth.request_token(authorization_code)["access_token"]
        character_id = eveonline.Auth.verify_token(access_token)["CharacterID"]

        state_data = db.StateToken.get(state)

        discord_user_id = state_data["discord_user_id"]
        interaction_token = state_data["interaction_token"]

        db.User.upsert(discord_user_id, character_id)
    except Exception:
        return show_error_page()

    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(
            {
                "discord_user_id": discord_user_id,
                "character_id": character_id,
            }
        ),
    )

    discord.Interaction.edit_original_message(
        interaction_token=interaction_token,
        components=[
            {
                "type": 10,
                "content": "## ✅ Vinculado com sucesso!\nAgora cadastre-se na Aliança e na Coalizão utilizando os botões abaixo:",
            },
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
            },
        ],
    )

    return show_confirmation_page(character_id)


def show_confirmation_page(character_id):
    html_content = f"""
<!DOCTYPE html>
<html lang="pt-BR">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Forcinha Bot - Sucesso</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                    Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #aeb0b4;
            }}

            .auth-popup {{
                background: #383a42;
                border-radius: 8px;
                box-shadow: 0 8px 16px rgba(0, 0, 0, 0.24);
                width: 480px;
                padding: 24px;
                text-align: center;
            }}

            .connection-visual  {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 32px;
                margin: 24px 0;
            }}

            .service-avatar  {{
                width: 80px;
                height: 80px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 2rem;
                font-weight: 600;
                position: relative;
            }}

            .discord-avatar  {{
                background-image: url(https://forcinha-bot-publico.s3.us-east-1.amazonaws.com/forcinha_profile.png);
                background-size: cover;
            }}

            .eve-avatar  {{
                background-image: url(https://images.evetech.net/characters/{character_id}/portrait?size=128);
                background-size: cover;
            }}

            .connection-dots  {{
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                color: #64656b;
            }}

            .success-message  {{
                background: #2f3136;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 24px;
            }}

            .success-item  {{
                display: flex;
                align-items: flex-start;
                gap: 12px;
                text-align: left;
                margin-bottom: 8px;
            }}

            .success-bullet  {{
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #3ba55c;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                color: white;
                flex-shrink: 0;
                margin-top: 2px;
            }}

            .success-content  {{
                flex: 1;
            }}

            .success-text  {{
                font-size: 16px;
                font-weight: 500;
                color: #dcddde;
                margin-bottom: 4px;
            }}

            .success-description  {{
                font-size: 12px;
                color: #b9bbbe;
                line-height: 1.4;
            }}

            .auth-footer  {{
                font-size: 12px;
                font-weight: 500;
                color: #72767d;
                text-align: center;
                align-items: center;
                padding-top: 1rem;
                border-top: #4d5057 1px solid;
                display: flex;
                justify-content: center;
                gap: 6px;
            }}
        </style>
    </head>
    <body>
        <div class="auth-popup">
            <div class="connection-visual">
                <div class="service-avatar discord-avatar"></div>
                <div class="connection-dots">⋯</div>
                <div class="service-avatar eve-avatar"></div>
            </div>

            <div class="success-message">
                <div class="success-item">
                    <div class="success-bullet">✓</div>
                    <div class="success-content">
                        <div class="success-text">Vinculado com Sucesso</div>
                        <div class="success-description">
                            <p>
                                Seu usuário Discord foi vinculado ao personagem
                                de EVE Online.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="auth-footer">
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >
                    <path d="m16 17 5-5-5-5" />
                    <path d="M21 12H9" />
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /></svg
                >Esta página já pode ser fechada.
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


def show_error_page():
    html_content = f"""
<!DOCTYPE html>
<html lang="pt-BR">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Forcinha Bot - Erro</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                    Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #aeb0b4;
            }}

            .auth-popup {{
                background: #383a42;
                border-radius: 8px;
                box-shadow: 0 8px 16px rgba(0, 0, 0, 0.24);
                width: 480px;
                padding: 24px;
                text-align: center;
            }}

            .connection-visual {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 32px;
                margin: 24px 0;
            }}

            .service-avatar {{
                width: 80px;
                height: 80px;
                border-radius: 50%;
                position: relative;
            }}

            .discord-avatar {{
                background-image: url(https://forcinha-bot-publico.s3.us-east-1.amazonaws.com/forcinha_profile.png);
                background-size: cover;
            }}

            .eve-avatar {{
                background: #ad5050;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                padding-bottom: 2px;
                color: white;
                flex-shrink: 0;
            }}

            .connection-dots {{
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 32px;
                color: #64656b;
            }}

            .error-message {{
                background: #2f3136;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 24px;
            }}

            .error-item {{
                display: flex;
                align-items: flex-start;
                gap: 12px;
                text-align: left;
                margin-bottom: 8px;
            }}

            .error-bullet {{
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #98999c;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                color: white;
                flex-shrink: 0;
                margin-top: 2px;
            }}

            .error-content {{
                flex: 1;
            }}

            .error-text {{
                font-size: 16px;
                font-weight: 500;
                color: #dcddde;
                margin-bottom: 4px;
            }}

            .error-description {{
                font-size: 12px;
                color: #b9bbbe;
                line-height: 1.4;
            }}

            .auth-footer {{
                font-size: 12px;
                font-weight: 500;
                color: #72767d;
                text-align: center;
                align-items: center;
                padding-top: 1rem;
                border-top: #4d5057 1px solid;
                display: flex;
                justify-content: center;
                gap: 6px;
            }}
        </style>
    </head>
    <body>
        <div class="auth-popup">
            <div class="connection-visual">
                <div class="service-avatar discord-avatar"></div>
                <div class="connection-dots">⋯</div>
                <div class="service-avatar eve-avatar">⨉</div>
            </div>

            <div class="error-message">
                <div class="error-item">
                    <div class="error-bullet">✖</div>
                    <div class="error-content">
                        <div class="error-text">Erro ao Vincular</div>
                        <div class="error-description">
                            <p>Não foi possível vincular as contas. Tente
                                novamente.</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="auth-footer">
                <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                >
                    <path d="m16 17 5-5-5-5" />
                    <path d="M21 12H9" />
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /></svg
                >Esta página já pode ser fechada.
            </div>
        </div>
    </body>
</html>
"""

    return {
        "statusCode": 400,
        "headers": {"Content-Type": "text/html"},
        "body": html_content,
    }
