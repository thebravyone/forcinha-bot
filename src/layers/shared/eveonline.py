import base64
import os
import urllib.parse

import requests

COMPATIBILITY_DATE = "2025-09-23"

EVE_CLIENT_ID = os.environ["EVE_CLIENT_ID"]
EVE_CLIENT_SECRET = os.environ["EVE_CLIENT_SECRET"]
SSO_CALLBACK_URL = os.environ.get("SSO_CALLBACK_URL", "")


class Auth:
    @staticmethod
    def generate_auth_url(state: str) -> str:
        query_string = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": EVE_CLIENT_ID,
                "redirect_uri": SSO_CALLBACK_URL,
                "scope": "publicData",
                "state": state,
            }
        )
        return f"https://login.eveonline.com/v2/oauth/authorize?{query_string}"

    @staticmethod
    def request_token(authorization_code: str):
        basic_auth = base64.urlsafe_b64encode(
            f"{EVE_CLIENT_ID}:{EVE_CLIENT_SECRET}".encode("utf-8")
        ).decode()

        response = requests.post(
            "https://login.eveonline.com/v2/oauth/token",
            headers={
                "Authorization": f"Basic {basic_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": authorization_code,
            },
        )

        response.raise_for_status()
        return response.json()

    @staticmethod
    def verify_token(access_token: str):
        response = requests.get(
            "https://esi.evetech.net/verify/",
            headers={
                "X-Compatibility-Date": COMPATIBILITY_DATE,
                "Authorization": f"Bearer {access_token}",
            },
        )

        response.raise_for_status()
        return response.json()


class Character:
    @staticmethod
    def get_character_data(character_id: int) -> dict:
        response = requests.get(
            f"https://esi.evetech.net/characters/{int(character_id)}",
            headers={"X-Compatibility-Date": COMPATIBILITY_DATE},
        )

        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_affiliation(character_ids: list[int]) -> list[dict]:
        if len(character_ids) == 0:
            return []

        character_ids = [int(id) for id in character_ids]

        response = requests.post(
            "https://esi.evetech.net/characters/affiliation",
            json=(character_ids),
            headers={"X-Compatibility-Date": COMPATIBILITY_DATE},
        )

        response.raise_for_status()
        return response.json()


class Corporation:
    @staticmethod
    def get_corporation_data(corporation_id: int) -> dict:
        response = requests.get(
            f"https://esi.evetech.net/corporations/{int(corporation_id)}",
            headers={"X-Compatibility-Date": COMPATIBILITY_DATE},
        )

        response.raise_for_status()
        return response.json()
