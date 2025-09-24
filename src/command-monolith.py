import json

import discord
import eveonline


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

        # if command_name == "auditar":
        #     return command_audit(body)

    return {
        "statusCode": 400,
        "body": "Bad Request",
    }


def command_link_account(command: dict):

    guild_user_id = command.get("member", {}).get("user", {}).get("id")
    dm_user_id = command.get("user", {}).get("id")

    discord_user_id = guild_user_id or dm_user_id

    if discord_user_id is None:
        raise ValueError("Could not determine discord user ID")

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
                    "url": eveonline.generate_auth_url(discord_user_id),
                }
            ],
        },
    ]

    discord.Interaction.create_message(
        original_command=command, components=components, ephemeral=True
    )

    return {"statusCode": 202}


# def command_audit(command: dict):

#     message_url = interaction_callback_url(command)

#     httpx.post(
#         message_url,
#         headers={"User-Agent": USER_AGENT},
#         json={
#             "type": 5,  # ACK with source
#         },
#     )

#     try:
#         response = httpx.get(
#             "https://r2zrcqmbzurqzwewqpeqsnfpoy0skysk.lambda-url.us-east-1.on.aws/",
#             timeout=60 * 5,  # 5 minutes
#         )
#         response.raise_for_status()
#         results = response.json()
#     except Exception as e:
#         print(e)
#         return {"statusCode": 500}

#     content = f"🔍  {results["audited_count"]} Membros Auditados\n"

#     total_issues = (
#         len(results["nicks_updated"])
#         + len(results["roles_added"])
#         + len(results["roles_removed"])
#         # + len(results["dm_sent"])
#     )

#     if total_issues == 0:
#         content += f"\n✅  Nenhum problema encontrado!"

#     embeds = []
#     if len(results["nicks_updated"]) > 0:
#         embeds.append(
#             {
#                 "title": f"{len(results['nicks_updated'])}  Nicknames Atualizados",
#                 "description": "\n".join(results["nicks_updated"]),
#                 "color": 0x0EA5E9,
#             }
#         )

#     if len(results["roles_added"]) > 0:
#         embeds.append(
#             {
#                 "title": f"{len(results['roles_added'])}  Roles Adicionadas",
#                 "description": "\n".join(results["roles_added"]),
#                 "color": 0x22C55E,
#             }
#         )

#     if len(results["roles_removed"]) > 0:
#         embeds.append(
#             {
#                 "title": f"{len(results['roles_removed'])}  Roles Removidas",
#                 "description": "\n".join(results["roles_removed"]),
#                 "color": 0xDC2626,
#             }
#         )

#     response = httpx.patch(
#         f"https://discord.com/api/v10/webhooks/{APP_ID}/{command["token"]}/messages/@original",
#         headers={"User-Agent": USER_AGENT},
#         json={
#             "content": content,
#             "embeds": embeds,
#         },
#     )

#     response.raise_for_status()

#     return {"statusCode": 202}
