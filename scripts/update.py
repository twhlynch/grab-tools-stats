import json
import math
import sys
from datetime import datetime, timedelta

import discord
import requests
import utils
from discord import Embed
from discord.ext import commands

BOT_TOKEN: str = sys.argv[1]
CF_ID: str = sys.argv[2]
CF_TOKEN: str = sys.argv[3]
NAMESPACE: str = sys.argv[4]
server_token_headers = json.loads(sys.argv[5])


def filter_level(level: utils.Level):
    # remove tags leaving "ok"
    if "tags" in level:
        if "ok" in level["tags"]:
            level["tags"] = ["ok"]
        else:
            del level["tags"]

    # remove most of the images data TODO: remove all and add image_iteration
    if "images" in level and isinstance(level["images"], dict):
        if "full" in level["images"]:
            del level["images"]["full"]
        if "thumb" in level["images"] and isinstance(level["images"]["thumb"], dict):
            if "width" in level["images"]["thumb"]:
                del level["images"]["thumb"]["width"]
            if "height" in level["images"]["thumb"]:
                del level["images"]["thumb"]["height"]

    # remove data key and override iteration
    if "data_key" in level:
        iteration = int(level["data_key"].split(":")[3])
        if iteration > 1:
            level["iteration"] = iteration

    # default values for statistics
    level["statistics"] = {**utils.MakeLevelStatistics(), **level.get("statistics", {})}

    # for some reason pyright is fine with removing required keys
    _ = level.pop("verification_time", None)
    _ = level.pop("format_version", None)
    _ = level.pop("description", None)
    _ = level.pop("data_key", None)


def filter_level_list(levels: list[utils.Level]) -> None:
    for level in levels:
        filter_level(level)


def get_level_list(list_type: str) -> list[utils.Level]:
    url: str = (
        f"{utils.SERVER_API}list?max_format_version={utils.FORMAT_VERSION}&type={list_type}"
    )

    response: requests.Response | None = utils.safe_get(
        url, headers=server_token_headers
    )
    levels: list[utils.Level] = utils.safe_json(response) or []

    filter_level_list(levels)
    return levels


def get_user_info(user_id: str) -> utils.User | None:
    url: str = f"{utils.SERVER_API}get_user_info?user_id={user_id}"

    response: requests.Response | None = utils.safe_get(
        url, headers=server_token_headers
    )
    data: utils.User | None = utils.safe_json(response)

    return data


def get_level_leaderboard(identifier: str) -> list[utils.Placement]:
    level_path: str = identifier.replace(":", "/")
    url: str = f"{utils.SERVER_API}statistics_top_leaderboard/{level_path}"

    response: requests.Response | None = utils.safe_get(
        url, headers=server_token_headers
    )
    data: list[utils.Placement] = utils.safe_json(response) or []

    return data


def get_level_stats(identifier: str) -> utils.Statistics:
    level_path: str = identifier.replace(":", "/")
    url: str = f"{utils.SERVER_API}statistics/{level_path}"

    response: requests.Response | None = utils.safe_get(
        url, headers=server_token_headers
    )
    data: utils.Statistics = utils.safe_json(response) or utils.MakeStatistics()

    return data


def get_level_browser() -> utils.LevelBrowser:
    url: str = f"{utils.SERVER_API}get_level_browser?version=1"

    response: requests.Response | None = utils.safe_get(
        url, headers=server_token_headers
    )
    data: utils.LevelBrowser | None = utils.safe_json(response)

    # this is required
    if data is None:
        sys.exit(0)

    return data


def get_user_name(user_id: str, potential_name: str, priority: bool = False) -> str:
    creators = utils.read_data("featured_creators")

    for creator in creators:
        if creator["list_key"].split(":")[1] == user_id:
            return creator["title"]

    if priority:
        user_data: utils.User | None = get_user_info(user_id)
        if user_data:
            return user_data["user_name"]

    return f"{potential_name}?"


def timestamp_to_days(
    timestamp_in_milliseconds: int, now: float | None = None
) -> float:
    now = now or datetime.now().timestamp() * 1000

    days: float = (now - timestamp_in_milliseconds) / 1000 / 60 / 60 / 24

    return days


def get_total_levels() -> dict[str, int]:
    url: str = f"{utils.SERVER_API}total_level_count?type=newest"

    response: requests.Response | None = utils.safe_get(
        url, headers=server_token_headers
    )

    if response is None:
        return {"levels": 0}  # probably fine

    count: int = int(response.text)

    return {"levels": count}


def get_all_verified(page_timestamp: str = "") -> list[utils.Level]:
    verified: list[utils.Level] = []

    while True:
        url: str = (
            f"{utils.SERVER_API}list?max_format_version={utils.FORMAT_VERSION}&type=ok&page_timestamp={page_timestamp}"
        )

        response: requests.Response | None = utils.safe_get(
            url, headers=server_token_headers
        )
        data: list[utils.Level] | None = utils.safe_json(response)

        if data is None:
            sys.exit(0)  # required

        # accumulate
        verified.extend(data)

        # get next page
        if len(data) > 0 and "page_timestamp" in data[-1]:
            page_timestamp = data[-1]["page_timestamp"]
        else:
            # no timestamp, end of list
            break

    filter_level_list(verified)
    return verified


def find_list_keys(data: utils.Section) -> list[str]:
    list_keys: list[str] = []

    title: str = data["title"]
    list_key: str | None = data.get("list_key", None)

    if title in ["Past Competitions", "Weekly Spotlight"]:
        return list_keys  # empty

    if list_key is None or list_key.startswith("curated_gab"):
        return list_keys  # empty

    list_keys.append(list_key)

    for section in data.get("sections", []):
        list_keys.extend(find_list_keys(section))

    return list_keys


def get_best_of_grab() -> list[utils.Level]:
    level_browser: utils.LevelBrowser = get_level_browser()
    all_list_keys: list[str] = [
        key for section in level_browser["sections"] for key in find_list_keys(section)
    ]

    levels: list[utils.Level] = []

    for list_key in all_list_keys:
        if list_key.startswith("curated_"):
            levels_list: list[utils.Level] = get_level_list(list_key)
            for level in levels_list:
                level["list_key"] = list_key
                leaderboard: list[utils.Placement] = get_level_leaderboard(
                    level["identifier"]
                )
                level["leaderboard"] = leaderboard
            for level in levels_list:
                found = False
                for level2 in levels:
                    if level2["identifier"] == level["identifier"]:
                        found = True
                        level2["list_key"] = (
                            level2["list_key"] + ":" + level["list_key"]
                        )
                        break
                if not found:
                    levels.append(level)

    return levels


def get_unbeaten(all_verified_maps, soles_data):
    unbeaten = []
    for level in all_verified_maps:
        days_old = timestamp_to_days(level["creation_timestamp"])
        exceptions = []  # check anyway
        hacked = []
        if level["statistics"]["difficulty"] == 0 and (
            (days_old > 1 and level["statistics"]["total_played"] > 300)
            or days_old > 10
        ):
            stats = get_level_stats(level["identifier"])
            if stats["finished_count"] == 0:
                if "creators" not in level:
                    level["creators"] = ["?"]
                unbeaten.append(level)
            # handle verification runs (and hacked)
            elif stats["finished_count"] == 1 or level["identifier"] in hacked:
                leaderboard = get_level_leaderboard(level["identifier"])
                if len(leaderboard) == 0:
                    if "creators" not in level:
                        level["creators"] = ["?"]
                    unbeaten.append(level)
        elif level["identifier"] in exceptions:
            stats = get_level_stats(level["identifier"])
            if stats["finished_count"] == 0:
                if "creators" not in level:
                    level["creators"] = ["?"]
                unbeaten.append(level)
        else:
            potential_diff = False
            potential_sole = False
            if (
                level["statistics"]["difficulty"] * level["statistics"]["total_played"]
                < 2
            ):
                potential_diff = True
            for level2 in soles_data:
                if (
                    level2["identifier"] == level["identifier"]
                    and level["identifier"].split(":")[0]
                    == level2["leaderboard"][0]["user_id"]
                ):
                    potential_sole = True
                    break
            if potential_sole and potential_diff:
                level["sole"] = True
                unbeaten.append(level)
    return unbeaten[::-1]


def get_most_verified(all_verified_maps, old_data):
    most_verified = {}

    for level in all_verified_maps:
        user_identifier = level["identifier"].split(":")[0]
        if user_identifier not in most_verified:
            most_verified[user_identifier] = {"count": 0}
        most_verified[user_identifier]["count"] += 1

    most_verified = sorted(
        most_verified.items(), key=lambda x: x[1]["count"], reverse=True
    )

    potentials = {t[0]: t[1] for t in most_verified[10:][:190]}
    most_verified = {t[0]: t[1] for t in most_verified[:10]}

    for user_identifier in most_verified:
        user_data = get_user_info(user_identifier)
        most_verified[user_identifier]["user_name"] = user_data["user_name"]
        most_verified[user_identifier]["levels"] = user_data["user_level_count"]

    for user_identifier in potentials:
        for level in all_verified_maps:
            if user_identifier == level["identifier"].split(":")[0]:
                potential_name = ""
                if "creators" in level and level["creators"]:
                    potential_name = level["creators"][0]
                potentials[user_identifier]["user_name"] = get_user_name(
                    user_identifier, potential_name
                )
                break
        potentials[user_identifier]["levels"] = potentials[user_identifier]["count"]

    most_verified |= potentials

    for user_identifier in most_verified:
        if user_identifier in old_data:
            most_verified[user_identifier]["change"] = (
                most_verified[user_identifier]["count"]
                - old_data[user_identifier]["count"]
            )
        else:
            most_verified[user_identifier]["change"] = 0

    return most_verified


def get_most_plays(all_verified_maps, old_data):
    most_plays = {}

    for level in all_verified_maps:
        user_identifier = level["identifier"].split(":")[0]
        if user_identifier not in most_plays:
            most_plays[user_identifier] = {"plays": 0, "count": 0}
        most_plays[user_identifier]["plays"] += level["statistics"]["total_played"]
        most_plays[user_identifier]["count"] += 1

    most_plays = sorted(most_plays.items(), key=lambda x: x[1]["plays"], reverse=True)
    potentials = {t[0]: t[1] for t in most_plays[10:][:190]}
    most_plays = {t[0]: t[1] for t in most_plays[:10]}

    for user_identifier in potentials:
        for level in all_verified_maps:
            if user_identifier == level["identifier"].split(":")[0]:
                potential_name = ""
                if "creators" in level and level["creators"]:
                    potential_name = level["creators"][0]
                potentials[user_identifier]["user_name"] = get_user_name(
                    user_identifier, potential_name
                )
                break
        potentials[user_identifier]["levels"] = potentials[user_identifier]["count"]

    for user_identifier in most_plays:
        user_data = get_user_info(user_identifier)
        most_plays[user_identifier]["user_name"] = user_data["user_name"]
        most_plays[user_identifier]["levels"] = user_data["user_level_count"]

    most_plays |= potentials

    for user_identifier in most_plays:
        if user_identifier in old_data:
            most_plays[user_identifier]["change"] = (
                most_plays[user_identifier]["plays"]
                - old_data[user_identifier]["plays"]
            )
        else:
            most_plays[user_identifier]["change"] = 0
    return most_plays


def get_trending_info(all_verified, old_data):
    for level in all_verified:
        old_level = False
        for old_level_i in old_data:
            if level["identifier"] == old_level_i["identifier"]:
                old_level = old_level_i

        if old_level:
            level["change"] = (
                level["statistics"]["total_played"]
                - old_level["statistics"]["total_played"]
            )
        else:
            level["change"] = level["statistics"]["total_played"]


def get_beaten_unbeaten(levels_old):
    beaten = []
    for old_level in levels_old:
        if "sole" not in old_level:
            leaderboard = get_level_leaderboard(old_level["identifier"])
            if len(leaderboard) > 0:
                leaderboard = sorted(leaderboard, key=lambda x: x["timestamp"])
                victor = leaderboard[0]
                title = old_level["title"]
                url = f"{utils.VIEWER_URL}?level={old_level['identifier']}"
                time = str(timedelta(seconds=victor["best_time"]))
                user = victor["user_name"]
                days = timestamp_to_days(old_level["update_timestamp"])
                extra = ""
                if old_level["update_timestamp"] != old_level["creation_timestamp"]:
                    extra = f" ({math.floor(timestamp_to_days(old_level["creation_timestamp"]))} since creation)"
                color = utils.Colors.YELLOW
                if timestamp_to_days(old_level["creation_timestamp"]) >= 100:
                    color = utils.Colors.ORANGE
                if timestamp_to_days(old_level["creation_timestamp"]) >= 365:
                    color = utils.Colors.RED
                if timestamp_to_days(old_level["creation_timestamp"]) >= 1000:
                    color = utils.Colors.WHITE
                beaten.append([title, user, time, days, url, extra, color])
    return beaten


def get_hardest_levels_list():
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/storage/kv/namespaces/{NAMESPACE}/values/list"
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.request("GET", url, headers=headers)
    return json.loads(response.text)


def get_hardest_levels_changes():
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/storage/kv/namespaces/{NAMESPACE}/values/list_changes"
    response = requests.request(
        "GET",
        url,
        headers={
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json",
        },
    )

    requests.put(url, headers={"Authorization": f"Bearer {CF_TOKEN}"}, data="[]")
    print("CHANGES", response.text)

    return json.loads(response.text)


def get_unverified(all_verified, all_verified_old):
    unverified = []
    verified_ids = [level["identifier"] for level in all_verified]
    for level in all_verified_old:
        if level["identifier"] not in verified_ids:
            unverified.append(level)
    return unverified


def build_embeds(
    unbeaten_levels,
    beaten_unbeaten_levels,
    unverified,
    best_of_grab_levels_old,
    best_of_grab_levels,
    hardest_levels_changes,
) -> dict[int, list[Embed]]:
    embeds: dict[int, list[Embed]] = {
        utils.Discord.Channels.HARDEST_LIST_UPDATES: [],
        utils.Discord.Channels.UNBEATEN_LEVELS_UPDATES: [],
        utils.Discord.Channels.UNVERIFICATION_LOGS: [],
        utils.Discord.Channels.CHALLENGE_UPDATES: [],
        utils.Discord.Channels.RECORDS_LOGS: [],
    }

    # hardest list updates
    for change in hardest_levels_changes:
        embed = Embed(
            title=change["title"],
            url=f"{utils.VIEWER_URL}?level={change['id']}",
            description=f"{change['title']} by {change['creator']}\n{change["description"]} {change["i"] + 1}",
            color=utils.Colors.WHITE if change["i"] == 0 else utils.Colors.RED,
        )
        embeds[utils.Discord.Channels.HARDEST_LIST_UPDATES].append(embed)

    # unbeaten levels
    if unbeaten_levels:
        embed = Embed(
            title="Unbeaten Levels Update",
            url=f"{utils.WEBSITE_URL}stats?tab=UnbeatenMaps",
            description="Unbeaten Update",
            color=utils.Colors.CYAN,
        )
        embed.add_field(name="Count", value=str(len(unbeaten_levels)))

        over_100 = []

        for level in unbeaten_levels:
            if timestamp_to_days(level["update_timestamp"]) >= 100:
                over_100.append(level)

        if over_100:
            embed.add_field(
                name="Over 100 Days",
                value=("\n".join([f"{level['title']}" for level in over_100]))[:900],
                inline=False,
            )

        if len(unbeaten_levels) > 0:
            embed.add_field(
                name="Newest", value=unbeaten_levels[-1]["title"], inline=False
            )

        embeds[utils.Discord.Channels.UNBEATEN_LEVELS_UPDATES].append(embed)

    for beaten in beaten_unbeaten_levels:
        beaten_embed = Embed(
            title=beaten[0],
            url=beaten[4],
            description=f"Beaten by {beaten[1]} in {beaten[2]} after {math.floor(beaten[3])} days!{beaten[5]}",
            color=beaten[6],
        )
        embeds[utils.Discord.Channels.UNBEATEN_LEVELS_UPDATES].append(beaten_embed)

    for map in unverified:
        color = utils.Colors.BLACK
        creator = "Unknown Creator"
        if "scheduled_for_deletion" in map:
            color = utils.Colors.RED
        if "creators" in map and len(map["creators"]) > 0:
            creator = map["creators"][0]
        unverified_embed = Embed(
            title=map["title"],
            url=f"{utils.VIEWER_URL}?level={map['identifier']}",
            description=creator,
            color=color,
        )
        if (
            "images" in map
            and "thumb" in map["images"]
            and "key" in map["images"]["thumb"]
        ):
            link = map["images"]["thumb"]["key"]
            unverified_embed.set_thumbnail(url=f"https://grab-images.slin.dev/{link}")

        embeds[utils.Discord.Channels.UNVERIFICATION_LOGS].append(unverified_embed)

    # challenge maps record changes
    new_records = []
    for map in best_of_grab_levels:
        found = False
        for map_old in best_of_grab_levels_old:
            if (
                map["identifier"] == map_old["identifier"]
                and "curated_challenge" in map["list_key"]
            ):
                found = True
                old_record = None
                current_record = None
                if "leaderboard" in map_old and len(map_old["leaderboard"]) > 0:
                    old_record = map_old["leaderboard"][0]
                if "leaderboard" in map and len(map["leaderboard"]) > 0:
                    current_record = map["leaderboard"][0]
                if (
                    current_record is not None
                    and old_record is not None
                    and current_record["timestamp"] != old_record["timestamp"]
                ):
                    embed = Embed(
                        title=map["title"],
                        url=f"{utils.VIEWER_URL}?level={map['identifier']}",
                        description=f"New record by {current_record['user_name']}: {current_record["best_time"]}s",
                        color=utils.Colors.RED,
                    )
                    embeds[utils.Discord.Channels.CHALLENGE_UPDATES].append(embed)
                elif current_record is not None and old_record is not None:
                    break
                elif current_record is not None and old_record is None:
                    embed = Embed(
                        title=map["title"],
                        url=f"{utils.VIEWER_URL}?level={map['identifier']}",
                        description=f"New record by {current_record['user_name']}: {current_record["best_time"]}s",
                        color=utils.Colors.RED,
                    )
                    embeds[utils.Discord.Channels.CHALLENGE_UPDATES].append(embed)
                elif old_record is not None:
                    embed = Embed(
                        title=map["title"],
                        url=f"{utils.VIEWER_URL}?level={map['identifier']}",
                        description="Record removed by moderator",
                        color=utils.Colors.DARK_RED,
                    )
                    embeds[utils.Discord.Channels.CHALLENGE_UPDATES].append(embed)
                break
        if not found and "curated_challenge" in map["list_key"]:
            embed = Embed(
                title=map["title"],
                url=f"{utils.VIEWER_URL}?level={map['identifier']}",
                description="Map added to a challenge",
                color=utils.Colors.DARK_RED,
            )
            embeds[utils.Discord.Channels.CHALLENGE_UPDATES].append(embed)

        limit = 100 if "curated_challenge" in map["list_key"] else 10
        for i in range(min(len(map["leaderboard"]), limit)):
            identifier = map["leaderboard"][i]["user_id"]
            for map_old in best_of_grab_levels_old:
                if map["identifier"] == map_old["identifier"]:
                    found = False
                    for j in range(min(len(map_old["leaderboard"]), limit)):
                        if map_old["leaderboard"][j]["user_id"] == identifier:
                            found = True
                            if (
                                map["leaderboard"][i]["timestamp"]
                                != map_old["leaderboard"][j]["timestamp"]
                            ):
                                new_records.append(
                                    {
                                        "identifier": map["identifier"],
                                        "title": map["title"],
                                        "record": map["leaderboard"][i],
                                    }
                                )
                    if not found:
                        new_records.append(
                            {
                                "identifier": map["identifier"],
                                "title": map["title"],
                                "record": map["leaderboard"][i],
                            }
                        )

    for entry in new_records:
        embed = Embed(
            title=entry["title"],
            url=f"{utils.VIEWER_URL}?level={entry['identifier']}",
            color=(
                utils.Colors.RED
                if int(entry["record"]["position"]) == 0
                else utils.Colors.DARK_RED
            ),
        )
        embed.add_field(
            name=entry["record"]["user_name"],
            value=f"{entry["record"]["position"]}: {entry["record"]['best_time']}s",
            inline=False,
        )
        embeds[utils.Discord.Channels.RECORDS_LOGS].append(embed)

    for map_old in best_of_grab_levels_old:
        if "curated_challenge" in map_old["list_key"]:
            found = False
            for map in best_of_grab_levels:
                if (
                    map["identifier"] == map_old["identifier"]
                    and "curated_challenge" in map["list_key"]
                ):
                    found = True
                    break
            if not found:
                embed = Embed(
                    title=map_old["title"],
                    url=f"{utils.VIEWER_URL}?level={map_old['identifier']}",
                    description="Map removed from a challenge",
                    color=utils.Colors.DARK_RED,
                )
                embeds[utils.Discord.Channels.CHALLENGE_UPDATES].append(embed)

    return embeds


def run_bot(embeds):
    # setup bot
    bot = commands.Bot(
        command_prefix="!",
        intents=discord.Intents.default(),
        allowed_mentions=discord.AllowedMentions(
            roles=True, users=False, everyone=False
        ),
    )

    @bot.event
    async def on_ready():
        # guild handles
        guild = bot.get_guild(utils.Discord.GUILD)

        unbeaten_levels_updates_channel = bot.get_channel(
            utils.Discord.Channels.UNBEATEN_LEVELS_UPDATES,
        )

        hardest_levels_role = guild.get_role(
            utils.Discord.Roles.HARDEST_LEVELS,
        )

        # send ping
        await unbeaten_levels_updates_channel.send(f"||{hardest_levels_role.mention}||")

        # send embeds
        for channel_id, channel_embeds in embeds.items():
            channel = bot.get_channel(channel_id)

            for embed in channel_embeds:
                channel.send(embed=embed)

        # close
        await bot.close()

    bot.run(BOT_TOKEN)


def main():
    # read required previous data
    most_plays_old = utils.read_data("most_plays")
    most_verified_old = utils.read_data("most_verified")
    unbeaten_levels_old = utils.read_data("unbeaten_levels")
    all_verified_old = utils.read_data("all_verified")
    best_of_grab_levels_old = utils.read_data("best_of_grab")
    sole_victors = utils.read_data("sole_victors")

    # run requests and data processing
    all_verified = get_all_verified()

    unbeaten_levels = get_unbeaten(all_verified, sole_victors)
    beaten_unbeaten_levels = get_beaten_unbeaten(unbeaten_levels_old)
    unverified = get_unverified(all_verified, all_verified_old)
    hardest_levels_list = get_hardest_levels_list()
    hardest_levels_changes = get_hardest_levels_changes()
    get_trending_info(all_verified, all_verified_old)
    best_of_grab_levels = get_best_of_grab()
    most_verified = get_most_verified(all_verified, most_verified_old)
    most_plays = get_most_plays(all_verified, most_plays_old)
    total_levels = get_total_levels()

    # save new data
    utils.write_data(all_verified, "all_verified")
    utils.write_data(best_of_grab_levels, "best_of_grab")
    utils.write_data(unbeaten_levels, "unbeaten_levels")
    utils.write_data(most_verified, "most_verified")
    utils.write_data(most_plays, "most_plays")
    utils.write_data(hardest_levels_list, "hardest_levels_list")
    utils.write_data(total_levels, "total_level_count")

    # get embeds
    embeds = build_embeds(
        unbeaten_levels,
        beaten_unbeaten_levels,
        unverified,
        best_of_grab_levels_old,
        best_of_grab_levels,
        hardest_levels_changes,
    )

    # run announcements
    run_bot(embeds)


if __name__ == "__main__":
    main()
