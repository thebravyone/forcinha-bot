import base64
import os
import re
import time
import urllib.parse

import jwt
import requests

COMPATIBILITY_DATE = "2026-04-10"

METADATA_URL = "https://login.eveonline.com/.well-known/oauth-authorization-server"
METADATA_CACHE_TIME = 300  # 5 minutes
ACCEPTED_ISSUERS = ("logineveonline.com", "https://login.eveonline.com")
EXPECTED_AUDIENCE = "EVE Online"

EVE_CLIENT_ID = os.environ["EVE_CLIENT_ID"]
EVE_CLIENT_SECRET = os.environ["EVE_CLIENT_SECRET"]
SSO_CALLBACK_URL = os.environ.get("SSO_CALLBACK_URL", "")

# Cache
esi_metadata = requests.get(METADATA_URL).json()
jwks_client = jwt.PyJWKClient(esi_metadata["jwks_uri"])


class Auth:
    @staticmethod
    def generate_auth_url(state: str) -> str:
        """Generates the SSO authorization URL for the user to authenticate.
        :param state: A unique state string to prevent CSRF attacks
        :returns: The URL to redirect the user for SSO authentication
        """
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
        """Exchanges the authorization code for an access token.

        :param authorization_code: The authorization code received from the SSO callback
        :returns: The token response containing the access token and other metadata
        """
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
    def validate_jwt_token(token):
        """Validates the JWT access token and returns the decoded claims.

        :param token: The JWT access token to validate
        :returns: The decoded claims if the token is valid
        """
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        return jwt.decode(
            token,
            key=signing_key.key,
            algorithms=[signing_key.algorithm_name],
            issuer=ACCEPTED_ISSUERS,
            audience=EXPECTED_AUDIENCE,
        )

    @staticmethod
    def claim_character_id_from_token(access_token: str) -> int | None:
        """Extracts the character ID from the access token claims.

        :param access_token: The access token to extract the character ID from
        :returns: The character ID if present, otherwise None
        """
        claims = Auth.validate_jwt_token(access_token)
        sub = claims.get("sub", "")
        match = re.search(r"CHARACTER:EVE:(\d+)", sub)
        return int(match.group(1)) if match else None


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


class Universe:
    @staticmethod
    def get_type_data(type_id: int) -> dict:
        response = requests.get(
            f"https://esi.evetech.net/universe/types/{int(type_id)}",
            headers={"X-Compatibility-Date": COMPATIBILITY_DATE},
        )

        response.raise_for_status()
        return response.json()
