import json
from datetime import datetime, timedelta, timezone

import datalake
import db
import discord
import eveonline
import everef
import polars as pl
from requests import HTTPError

MES = {
    1: "JANEIRO",
    2: "FEVEREIRO",
    3: "MARÇO",
    4: "ABRIL",
    5: "MAIO",
    6: "JUNHO",
    7: "JULHO",
    8: "AGOSTO",
    9: "SETEMBRO",
    10: "OUTUBRO",
    11: "NOVEMBRO",
    12: "DEZEMBRO",
}


def handler(event, context):

    update_killmails()

    if datetime.now(timezone.utc).date().day == 3:
        announce_monthly_hero_tackler()

    return {
        "statusCode": 200,
        "body": json.dumps("Killmails Evaluated!"),
    }


def update_killmails():

    remote_totals = everef.Killmail.fetch_totals()
    local_totals = datalake.Killmail.get_totals()

    dates_to_fetch = sorted(
        [
            datetime.strptime(date, "%Y%m%d").date()
            for date in remote_totals.keys()
            if remote_totals.get(date) > 0
            and remote_totals.get(date) != local_totals.get(date)
        ]
    )[-15:]

    if dates_to_fetch:
        for date in dates_to_fetch:
            killmail_data = everef.Killmail.fetch_killmails_from_date(date)
            datalake.Killmail.upsert(killmail_data)

        datalake.Killmail.set_totals(remote_totals)

    return


def announce_monthly_hero_tackler():

    # CHANNEL_ID = 1346269756256288963  # dev
    CHANNEL_ID = 633084705775943680  # prod

    TACKLER_SHIP_TYPES = [
        ## T1 Frigates
        608,  # Atron
        594,  # Incursus
        583,  # Condor
        602,  # Kestrel
        603,  # Merlin
        589,  # Executioner
        597,  # Punisher
        587,  # Rifter
        585,  # Slasher
        ## Faction Frigates
        17841,  # Federation Navy Comet
        17619,  # Caldari Navy Hookbill
        17703,  # Imperial Navy Slicer
        17812,  # Republic Fleet Firetail
        17928,  # Daredevil
        17932,  # Dramiel
        17924,  # Succubus
        33816,  # Garmur
        17930,  # Worm
        ## Interceptors
        11202,  # Ares
        11200,  # Taranis
        11196,  # Claw
        11198,  # Stiletto
        11176,  # Crow
        11178,  # Raptor
        11184,  # Crusader
        11186,  # Malediction
        ## Assault Frigates
        12044,  # Enyo
        11381,  # Harpy
        11379,  # Hawk
        12042,  # Ishkur
        11400,  # Jaguar
        11371,  # Wolf
        11393,  # Retribution
        11365,  # Vengeance
        ## Bait Frigates
        32880,  # Venture
        33697,  # Prospect
        37135,  # Endurance
        ## Stealth Bombers
    ]

    end_date = datetime.now().date().replace(day=1) - timedelta(days=1)
    start_date = end_date.replace(day=1)

    killmails = datalake.Killmail.get().filter(
        (pl.col("date") >= start_date) & (pl.col("date") <= end_date),
        (pl.col("is_loss") == False),
        (pl.col("victim_character_id").is_not_null()),
    )

    hero_tackler = (
        killmails.filter(
            pl.col("attacker_ship_type_id").is_in(TACKLER_SHIP_TYPES),
        )
        .group_by(["attacker_character_id", "attacker_ship_type_id"])
        .agg(
            [
                pl.n_unique("killmail_id").alias("kill_count"),
            ]
        )
        .sort("kill_count", descending=True)
        .group_by("attacker_character_id")
        .agg(
            [
                pl.sum("kill_count").alias("total_kill_count"),
                pl.first("attacker_ship_type_id").alias("main_ship_type_id"),
                pl.first("kill_count").alias("main_ship_kill_count"),
            ]
        )
        .sort("total_kill_count", descending=True)
    ).collect()

    hero_tackler_top3 = hero_tackler.head(3).to_dicts()

    hero_tackler_top3 = [
        {
            **char,
            "attacker_character_name": get_character_name(
                char["attacker_character_id"]
            ),
            "main_ship_type_name": get_ship_type_name(char["main_ship_type_id"]),
        }
        for char in hero_tackler_top3
    ]

    if hero_tackler_top3:
        components = [
            {
                "type": 9,  # section
                "components": [
                    {
                        "type": 10,  # markdown
                        "content": f"""@everyone
# HERO TACKLER
> {MES[start_date.month]} {start_date.year}

🎖️  **{hero_tackler_top3[0]['attacker_character_name']}** [{hero_tackler_top3[0]['main_ship_type_name']}]
        {hero_tackler_top3[0]['total_kill_count']} kills

       **{hero_tackler_top3[1]['attacker_character_name']}** [{hero_tackler_top3[1]['main_ship_type_name']}]
        {hero_tackler_top3[1]['total_kill_count']} kills

       **{hero_tackler_top3[2]['attacker_character_name']}** [{hero_tackler_top3[2]['main_ship_type_name']}]
        {hero_tackler_top3[2]['total_kill_count']} kills""",
                    },
                ],
                "accessory": {
                    "type": 11,  # thumbnail
                    "media": {
                        "url": f"https://images.evetech.net/characters/{hero_tackler_top3[0]['attacker_character_id']}/portrait"
                    },
                },
            }
        ]

        discord.Message.create_message(channel_id=CHANNEL_ID, components=components)

    return


def get_character_name(character_id: int) -> str:

    metadata = db.EntityMetadata.get(character_id)
    character_name = metadata.get("character_name") if metadata else None

    if character_name is None:
        try:
            character_data = eveonline.Character.get_character_data(character_id)
            character_name = character_data.get("name", "")
        except HTTPError as exc:
            if getattr(getattr(exc, "response", None), "status_code", None) == 404:
                character_name = "Deleted Character"
            else:
                raise

        db.EntityMetadata.upsert(
            id=character_id,
            data={
                "character_name": character_name,
            },
        )

    return character_name


def get_ship_type_name(type_id: int) -> str:

    metadata = db.EntityMetadata.get(type_id)
    type_name = metadata.get("type_name") if metadata else None

    if type_name is None:

        type_data = eveonline.Universe.get_type_data(type_id)
        type_name = type_data.get("name", "")

        db.EntityMetadata.upsert(
            id=type_id,
            data={
                "type_name": type_name,
                "group_id": type_data.get("group_id"),
                "category_id": type_data.get("category_id"),
            },
        )

    return type_name
