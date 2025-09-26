import json
from string import Template

import db
import discord
import eveonline
from aws_xray_sdk.core import patch_all
from requests.exceptions import HTTPError

patch_all()

GUILD_POLICIES = {
    # "Forcinha Test Server": {
    #     "guild_id": 1346269756256288960,
    #     "nicknames": {
    #         "default": {
    #             "template": Template("[$corporation_ticker] $character_name"),
    #         },
    #         "rules": {
    #             "FORCA": {
    #                 "corporations": [98028546],
    #                 "template": Template("$character_name"),
    #             },
    #         },
    #     },
    #     "roles": {
    #         "Membro": {
    #             "role_id": 1346269819393282150,
    #             "corporations": [98028546],  # FORCA
    #             "alliances": [],
    #         },
    #         "Aliado": {
    #             "role_id": 1346584727850713200,
    #             "corporations": [],
    #             "alliances": [
    #                 99003214,  # Brave Collective
    #                 99010079,  # Brave United
    #                 1354830081,  # Goonswarm Federation
    #             ],
    #         },
    #     },
    # },
    "FORCAS ARMADAS": {
        "guild_id": 189083933659365376,
        "nicknames": {
            "default": {
                "template": Template("[$corporation_ticker] $character_name"),
            },
            "rules": {
                "FORCA": {
                    "corporations": [98028546],
                    "template": Template("$character_name"),
                },
            },
        },
        "roles": {
            "Membro": {
                "role_id": 1063973360914145290,
                "corporations": [98028546],  # FORCA
                "alliances": [],
            },
            "Aliado": {
                "role_id": 1122778799839391895,
                "corporations": [],
                "alliances": [
                    99003214,  # Brave Collective
                    99010079,  # Brave United
                    1354830081,  # Goonswarm Federation
                ],
            },
        },
    },
}

GRAVEYARD_CORP_ID = 1000001  # The internal corporation used for characters in graveyard


def handler(event, context):

    if "Records" in event:
        users_to_audit = users_to_audit_from_sqs(event)  # event from SQS
    else:
        users_to_audit = all_users_all_guilds()  # scheduled or command

    logs = []
    for auditee in users_to_audit:
        logs.extend(audit_nickname(auditee))
        logs.extend(audit_roles(auditee))

    return {
        "statusCode": 200,
        "body": json.dumps(logs),
    }


def audit_nickname(auditee: dict) -> list[str] | None:

    if auditee["character"] is None:
        target_nickname = None
    else:
        character_name = auditee["character"].get("character_name", "")
        corporation_ticker = auditee["character"].get("corporation_ticker", "")

        nickname_template: Template | None = next(
            (
                rule["template"]
                for rule in auditee["guild_policy"]["nicknames"]["rules"].values()
                if auditee["character"]
                and auditee["character"].get("corporation_id")
                in rule.get("corporations", [])
            ),
            None,
        )

        if nickname_template is None:
            nickname_template: Template = auditee["guild_policy"]["nicknames"][
                "default"
            ]["template"]

        target_nickname = nickname_template.safe_substitute(
            character_name=character_name, corporation_ticker=corporation_ticker
        )

    current_nickname = auditee["guild_member"].get("nick", None)

    if current_nickname != target_nickname:
        try:
            discord.Guild.set_nickname(
                auditee["guild_policy"]["guild_id"],
                auditee["guild_member"]["user"]["id"],
                target_nickname,
            )
        except HTTPError:
            return [
                f"❌ Set nickname to `{target_nickname}` for `{auditee['guild_member']['nick'] or auditee['guild_member']['user']['global_name']}` failed"
            ]
        return [
            f"✅ Set nickname to `{target_nickname}` for `{auditee['guild_member']['nick'] or auditee['guild_member']['user']['global_name']}` succeeded"
        ]

    return []


def audit_roles(auditee: dict) -> list[str]:

    if auditee["character"] is None:
        target_role = None
    else:
        corporation_id = auditee["character"].get("corporation_id", None)
        alliance_id = auditee["character"].get("alliance_id", None)
        target_role = next(
            (
                rule["role_id"]
                for rule in auditee["guild_policy"]["roles"].values()
                if (
                    corporation_id is not None
                    and corporation_id in rule.get("corporations", [])
                )
                or (
                    alliance_id is not None and alliance_id in rule.get("alliances", [])
                )
            ),
            None,
        )

    target_roles = {str(target_role)} if target_role is not None else set()

    managed_roles = {
        str(rule["role_id"]) for rule in auditee["guild_policy"]["roles"].values()
    }

    current_roles = set(auditee["guild_member"].get("roles", [])) & managed_roles

    roles_to_add = target_roles - current_roles
    roles_to_remove = current_roles - target_roles

    logs = []
    role_name_map = {
        str(rule["role_id"]): key
        for key, rule in auditee["guild_policy"]["roles"].items()
    }

    for role_id in roles_to_add:
        try:
            discord.Guild.add_role(
                auditee["guild_policy"]["guild_id"],
                auditee["guild_member"]["user"]["id"],
                role_id,
            )
        except HTTPError:
            logs.append(
                f"❌ Add role `{role_name_map.get(role_id, role_id)}` to `{auditee['guild_member']['nick'] or auditee['guild_member']['user']['global_name']}` failed"
            )
            continue
        logs.append(
            f"✅ Add role `{role_name_map.get(role_id, role_id)}` to `{auditee['guild_member']['nick'] or auditee['guild_member']['user']['global_name']}` succeeded"
        )

    for role_id in roles_to_remove:
        try:
            discord.Guild.remove_role(
                auditee["guild_policy"]["guild_id"],
                auditee["guild_member"]["user"]["id"],
                role_id,
            )
        except HTTPError:
            logs.append(
                f"❌ Remove role `{role_name_map.get(role_id, role_id)}` from `{auditee['guild_member']['nick'] or auditee['guild_member']['user']['global_name']}` failed"
            )
            continue
        logs.append(
            f"✅ Remove role `{role_name_map.get(role_id, role_id)}` from `{auditee['guild_member']['nick'] or auditee['guild_member']['user']['global_name']}` succeeded"
        )

    return logs


def users_to_audit_from_sqs(event) -> list[dict]:

    users_from_records = [json.loads(record["body"]) for record in event["Records"]]

    character_ids = list(set([user["character_id"] for user in users_from_records]))
    characters_data = get_characters_data(character_ids)

    users_to_audit = []
    for user in users_from_records:

        character_data = characters_data.get(user.get("character_id", 0), None)

        for guild_policy in GUILD_POLICIES.values():

            # Check if user is in this guild
            try:
                guild_member = discord.Guild.get_member(
                    guild_policy["guild_id"], user["discord_user_id"]
                )
            except HTTPError as exc:
                if getattr(getattr(exc, "response", None), "status_code", None) == 404:
                    # Not found in this guild — skip
                    guild_member = None
                    continue
                raise

            if guild_member is not None:
                users_to_audit.append(
                    {
                        "guild_policy": guild_policy,
                        "guild_member": guild_member,
                        "character": character_data,
                    }
                )

    return users_to_audit


def all_users_all_guilds() -> list[dict]:

    registered_characters = db.User.get_all()
    characters_ids = list(
        set(
            [
                user["character_id"]
                for user in registered_characters
                if user.get("character_id") is not None
            ]
        )
    )

    characters_data = get_characters_data(characters_ids)

    users_to_audit = []
    for guild_policy in GUILD_POLICIES.values():

        discord_members = [
            member
            for member in discord.Guild.list_members(guild_policy["guild_id"])
            if not member["user"].get("bot", False)
        ]

        for member in discord_members:
            character_id = next(
                (
                    user["character_id"]
                    for user in registered_characters
                    if str(user["discord_user_id"]) == str(member["user"]["id"])
                ),
                None,
            )

            if character_id is None:
                character_data = None
            else:
                character_data = characters_data.get(character_id, None)

            users_to_audit.append(
                {
                    "guild_policy": guild_policy,
                    "guild_member": member,
                    "character": character_data,
                }
            )

    return users_to_audit


def get_characters_data(character_ids: list[int]) -> dict[int, dict]:
    """
    Retrieves detailed data for a list of EVE Online character IDs, including their affiliations, character names, and corporation tickers.
    Args:
        character_ids (list[int]): A list of EVE Online character IDs.
    Returns:
        dict[int, dict]: A dictionary mapping each character ID to a dictionary containing:
            - 'character_id': the character's ID,
            - 'character_name': the character's name,
            - 'corporation_id': the ID of the corporation the character belongs to,
            - 'corporation_ticker': the ticker of the character's corporation.
            - 'alliance_id': the ID of the alliance the character belongs to (if any).
        If a character's data is not found, the value will be None.
    """
    affiliations = eveonline.Character.get_affiliation(list(character_ids))

    corporation_ids = list(set([char["corporation_id"] for char in affiliations]))

    character_names = {
        char_id: get_character_name(char_id) for char_id in character_ids
    }

    corporation_tickers = {
        corp_id: get_corporation_ticker(corp_id) for corp_id in corporation_ids
    }

    character_data = {}
    for character_id in character_ids:
        character_data[character_id] = next(
            (
                {
                    **aff,
                    "character_name": character_names.get(aff["character_id"], ""),
                    "corporation_ticker": corporation_tickers.get(
                        aff["corporation_id"], ""
                    ),
                }
                for aff in affiliations
                if aff["character_id"] == character_id
                and aff["corporation_id"]
                != GRAVEYARD_CORP_ID  # TODO create alert for it
            ),
            None,
        )

    return character_data


def get_corporation_ticker(corporation_id: int) -> str:

    metadata = db.EntityMetadata.get(corporation_id)
    if metadata:
        return metadata["data"].get("ticker", "")

    try:
        corporation_data = eveonline.Corporation.get_corporation_data(corporation_id)
        ticker = corporation_data.get("ticker", "")
    except HTTPError as exc:
        if getattr(getattr(exc, "response", None), "status_code", None) == 404:
            ticker = "Deleted Corporation"
        else:
            raise

    db.EntityMetadata.upsert(
        id=corporation_id,
        data={
            "ticker": ticker,
            "corporation_name": corporation_data.get("name", ""),
        },
    )

    return ticker


def get_character_name(character_id: int) -> str:

    metadata = db.EntityMetadata.get(character_id)
    if metadata:
        return metadata["data"].get("character_name", "")

    try:
        character_data = eveonline.Character.get_character_data(character_id)
        name = character_data.get("name", "")
    except HTTPError as exc:
        if getattr(getattr(exc, "response", None), "status_code", None) == 404:
            name = "Deleted Character"
        else:
            raise

    db.EntityMetadata.upsert(
        id=character_id,
        data={
            "character_name": name,
        },
    )

    return name


if __name__ == "__main__":
    handler({}, {})
