import json
import os

import boto3
import db
import discord
import eveonline
from aws_xray_sdk.core import patch_all

patch_all()

AUDITFUNCTION_FUNCTION_NAME = os.environ.get("AUDITFUNCTION_FUNCTION_NAME")

lambda_client = boto3.client("lambda")


def handler(event, context):

    if not discord.verify_signature(event):
        return {"statusCode": 401, "body": "Invalid request signature"}

    command = json.loads(event.get("body", "{}"))
    interaction_type = command.get("type", 0)

    if interaction_type == 1:  # PING
        return discord.pong()

    if interaction_type == 2:  # Command
        command_name = command["data"]["name"]

        if command_name == "vincular":
            return command_link_account(command)

        if command_name == "auditar":
            return command_audit(command)

    return {
        "statusCode": 400,
        "body": "Bad Request",
    }


def command_link_account(command: dict):

    interaction_id = command["id"]
    interaction_token = command["token"]

    guild_user_id = command.get("member", {}).get("user", {}).get("id")
    dm_user_id = command.get("user", {}).get("id")

    discord_user_id = guild_user_id or dm_user_id

    if discord_user_id is None:
        raise ValueError("Could not determine discord user ID")

    state = db.StateToken.add(discord_user_id, interaction_token)

    components = [
        {
            "type": 10,  # ComponentType.TEXT_DISPLAY
            "content": "Clique no botão abaixo para vincular sua conta do EVE Online.",
        },
        {
            "type": 1,  # ComponentType.ACTION_ROW
            "components": [
                {
                    "type": 2,  # ComponentType.BUTTON
                    "style": 5,
                    "label": "Log in with EVE Online",
                    "url": eveonline.Auth.generate_auth_url(state),
                }
            ],
        },
    ]

    discord.Interaction.create_message(
        interaction_id=interaction_id,
        interaction_token=interaction_token,
        components=components,
        ephemeral=True,
    )

    return {"statusCode": 202}


def command_audit(command: dict):

    interaction_token = command["token"]

    discord.Interaction.create_message(
        interaction_id=command["id"],
        interaction_token=command["token"],
        components=None,
        type=5,
        ephemeral=True,
    )

    response = lambda_client.invoke(
        FunctionName=AUDITFUNCTION_FUNCTION_NAME,
        InvocationType="RequestResponse",
    )

    if response.get("StatusCode") != 200:
        return {"statusCode": 500, "body": "Failed to invoke audit function"}

    payload = json.load(response["Payload"])
    logs = json.loads(payload.get("body", []))

    if len(logs) == 0:
        logs_markdown = (
            "## Auditoria concluída\n\nNão houve ações corretivas necessárias"
        )

    else:
        logs_markdown = "## Auditoria concluída\n\n" + "\n".join(logs)

    discord.Interaction.edit_original_message(
        interaction_token=interaction_token,
        components=[
            {
                "type": 10,
                "content": logs_markdown,
            },
        ],
    )

    return {"statusCode": 202}
