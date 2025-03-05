import os

import httpx

APP_ID = os.environ.get("APP_ID", None)
BOT_TOKEN = os.environ.get("BOT_TOKEN", None)

url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"
headers = {"Authorization": f"Bot {BOT_TOKEN}"}

commands = [
    {
        "name": "vincular",
        "type": 1,
        "description": "Vincule sua conta do EVE-Online ao Discord",
        "contexts": [1],  # DM Only
    },
    {
        "name": "auditar",
        "type": 1,
        "description": "Auditar roles e o vínculo de contas do EVE-Online",
        "contexts": [0],
    },
]


def main():
    for command in commands:
        response = httpx.post(url, headers=headers, json=command)
        print(response.json())
    return


def delete_command(command_id: str):
    url = f"https://discord.com/api/v10/applications/{APP_ID}/commands/{command_id}"
    httpx.delete(url, headers=headers)
    return


if __name__ == "__main__":
    main()
    pass
