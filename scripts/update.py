import json
import math
import sys
from datetime import datetime, timedelta
from typing import NotRequired, TypedDict

import discord
import requests
import utils
from discord import Embed, Guild, Role, Thread
from discord.abc import GuildChannel, Messageable, PrivateChannel
from discord.ext import commands


BOT_TOKEN: str = sys.argv[1]
CF_ID: str = sys.argv[2]
CF_TOKEN: str = sys.argv[3]
NAMESPACE: str = sys.argv[4]
server_token_headers = json.loads(sys.argv[5])


def filter_level(level: utils.Level) -> None:
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
                            level2.get("list_key", "") + ":" + level.get("list_key", "")
                        )
                        break
                if not found:
                    levels.append(level)

    return levels


def get_unbeaten(all_verified_maps: list[utils.Level]) -> list[utils.Level]:
    unbeaten: list[utils.Level] = []

    for level in all_verified_maps:
        timestamp: int = level.get("creation_timestamp", 0)
        identifier: str = level["identifier"]
        days_old: float = timestamp_to_days(timestamp)

        statistics: utils.LevelStatistics = (
            level.get("statistics") or utils.MakeLevelStatistics()
        )

        difficulty: float = statistics.get("difficulty", 1.0)
        total_played: int = statistics.get("total_played", 0)

        enough_data: bool = (days_old > 1 and total_played > 300) or days_old > 10

        if difficulty == 0 and enough_data:
            # get full stats
            stats: utils.Statistics = get_level_stats(identifier)

            finished_count: int = stats["finished_count"]

            # unbeaten
            if finished_count == 0:
                unbeaten.append(level)

            # only verification run
            elif finished_count == 1:
                leaderboard: list[utils.Placement] = get_level_leaderboard(identifier)
                empty: bool = len(leaderboard) > 0

                first_entry: utils.Placement | None = empty and leaderboard[0] or None
                verification: bool | None = first_entry and (
                    identifier.split(":")[0] == first_entry["user_id"]
                )

                if empty or verification:
                    unbeaten.append(level)

    return unbeaten[::-1]  # old to new order


class MostVerified(TypedDict):
    count: int
    user_name: NotRequired[str]
    levels: NotRequired[int]
    change: NotRequired[int]


def get_most_verified(
    all_verified_maps: list[utils.Level], old_data: dict[str, MostVerified]
) -> dict[str, MostVerified]:
    verified_counts: dict[str, MostVerified] = {}

    # sum user_id -> map count
    for level in all_verified_maps:
        user_id: str = level["identifier"].split(":")[0]
        if user_id not in verified_counts:
            verified_counts[user_id] = {"count": 0}

        verified_counts[user_id]["count"] += 1

    # sort by count descending
    sorted_list: list[tuple[str, MostVerified]] = sorted(
        verified_counts.items(), key=lambda x: x[1]["count"], reverse=True
    )

    # top 0 - 10
    most_verified: dict[str, MostVerified] = {k: v for k, v in sorted_list[:10]}
    # top 10 - 200
    potentials: dict[str, MostVerified] = {k: v for k, v in sorted_list[10:][:190]}

    # add username and level count to entries
    for user_id, data in most_verified.items():
        user_data: utils.User | None = get_user_info(user_id)
        if user_data:
            data["user_name"] = user_data["user_name"]
            data["levels"] = user_data.get("user_level_count", 0)

    # try to add username without making request
    for user_id in potentials:
        for level in all_verified_maps:
            if user_id == level["identifier"].split(":")[0]:
                potential_name = ""
                if "creators" in level and level["creators"]:
                    potential_name: str = level["creators"][0]
                potentials[user_id]["user_name"] = get_user_name(
                    user_id, potential_name
                )
                break
        # use count as levels
        potentials[user_id]["levels"] = potentials[user_id]["count"]

    # combine with potentials
    most_verified |= potentials

    # add change if possible
    for user_id in most_verified:
        if user_id in old_data:
            most_verified[user_id]["change"] = (
                most_verified[user_id]["count"] - old_data[user_id]["count"]
            )
        else:
            most_verified[user_id]["change"] = 0

    return most_verified


class MostPlays(TypedDict):
    plays: int
    count: int
    levels: NotRequired[int]
    user_name: NotRequired[str]
    change: NotRequired[int]


def get_most_plays(
    all_verified_maps: list[utils.Level], old_data: dict[str, MostPlays]
) -> dict[str, MostPlays]:
    plays_counts: dict[str, MostPlays] = {}

    # sum user_id -> map count, plays total
    for level in all_verified_maps:
        user_id: str = level["identifier"].split(":")[0]
        if user_id not in plays_counts:
            plays_counts[user_id] = {"plays": 0, "count": 0}

        statistics: utils.LevelStatistics = level.get(
            "statistics", utils.MakeLevelStatistics()
        )
        plays_counts[user_id]["plays"] += statistics.get("total_played", 0)
        plays_counts[user_id]["count"] += 1

    # sort by plays descending
    sorted_list: list[tuple[str, MostPlays]] = sorted(
        plays_counts.items(), key=lambda x: x[1]["plays"], reverse=True
    )

    # top 0 - 10
    most_plays: dict[str, MostPlays] = {k: v for k, v in sorted_list[:10]}
    # top 10 - 200
    potentials: dict[str, MostPlays] = {k: v for k, v in sorted_list[10:][:190]}

    # add username and level count to entries
    for user_id, data in most_plays.items():
        user_data: utils.User | None = get_user_info(user_id)
        if user_data:
            data["user_name"] = user_data["user_name"]
            data["levels"] = user_data.get("user_level_count", 0)

    # try to add username without making request
    for user_id in potentials:
        for level in all_verified_maps:
            if user_id == level["identifier"].split(":")[0]:
                potential_name = ""
                if "creators" in level and level["creators"]:
                    potential_name: str = level["creators"][0]
                potentials[user_id]["user_name"] = get_user_name(
                    user_id, potential_name
                )
                break
        # use count as levels
        potentials[user_id]["levels"] = potentials[user_id]["count"]

    # combine with potentials
    most_plays |= potentials

    # add change if possible
    for user_id in most_plays:
        if user_id in old_data:
            most_plays[user_id]["change"] = (
                most_plays[user_id]["plays"] - old_data[user_id]["plays"]
            )
        else:
            most_plays[user_id]["change"] = 0

    return most_plays


def add_trending_info(
    all_verified: list[utils.Level], old_data: list[utils.Level]
) -> None:
    for level in all_verified:
        # find old level
        old_level: utils.Level | None = None
        for old_level_i in old_data:
            if level["identifier"] == old_level_i["identifier"]:
                old_level = old_level_i

        statistics: utils.LevelStatistics = level.get(
            "statistics", utils.MakeLevelStatistics()
        )

        # calculate change
        if old_level:
            old_statistics: utils.LevelStatistics = old_level.get(
                "statistics", utils.MakeLevelStatistics()
            )
            level["change"] = statistics.get("total_played", 0) - old_statistics.get(
                "total_played", 0
            )

        # or fallback to count
        else:
            level["change"] = statistics.get("total_played", 0)


class BeatenUnbeaten(TypedDict):
    title: str
    user: str
    time: str
    days: int
    url: str
    extra: str
    color: int


def get_beaten_unbeaten(levels_old: list[utils.Level]) -> list[BeatenUnbeaten]:
    beaten: list[BeatenUnbeaten] = []

    for old_level in levels_old:
        identifier: str = old_level["identifier"]

        leaderboard: list[utils.Placement] = get_level_leaderboard(identifier)
        if len(leaderboard) == 0:
            continue

        title: str = old_level.get("title", "")
        creation_timestamp: int = old_level.get("creation_timestamp", 0)
        update_timestamp: int = old_level.get("update_timestamp", 0)

        creation_days: float = timestamp_to_days(creation_timestamp)
        update_days: float = timestamp_to_days(update_timestamp)

        # get oldest record
        leaderboard = sorted(leaderboard, key=lambda x: x["timestamp"])
        victor: utils.Placement = leaderboard[0]

        url: str = f"{utils.VIEWER_URL}?level={old_level['identifier']}"
        time: str = str(timedelta(seconds=victor["best_time"]))
        user: str = victor["user_name"]
        days: int = math.floor(timestamp_to_days(update_timestamp))

        extra: str = ""
        if update_timestamp != creation_timestamp:
            extra = f" ({math.floor(creation_days)} since creation)"

        # color based on age
        color = utils.Colors.YELLOW
        if update_days >= 100:
            color = utils.Colors.ORANGE
        if update_days >= 365:
            color = utils.Colors.RED
        if update_days >= 1000:
            color = utils.Colors.WHITE

        item: BeatenUnbeaten = {
            "title": title,
            "user": user,
            "time": time,
            "days": days,
            "url": url,
            "extra": extra,
            "color": color,
        }
        beaten.append(item)

    return beaten


def get_hardest_levels_list():
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ID}/storage/kv/namespaces/{NAMESPACE}/values/list"
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.request("GET", url, headers=headers)
    return json.loads(response.text)


class Field(TypedDict):
    name: str
    value: str
    inline: bool


def make_embed(title: str, description: str, url: str, color: int) -> Embed:
    embed: Embed = Embed(
        title=title,
        url=url,
        description=description,
        color=color,
    )

    return embed


def unbeaten_levels_embeds(levels: list[utils.Level]) -> list[Embed]:
    embeds: list[Embed] = []

    if not levels:
        return embeds

    embed: Embed = make_embed(
        "Unbeaten Levels Update",
        "Unbeaten Update",
        f"{utils.WEBSITE_URL}stats?tab=UnbeatenMaps",
        utils.Colors.CYAN,
    )

    _ = embed.add_field(name="Count", value=str(len(levels)))

    over_100: list[utils.Level] = []

    for level in levels:
        if timestamp_to_days(level.get("update_timestamp", 0)) >= 100:
            over_100.append(level)

    if len(over_100) > 0:
        level_names: str = ("\n".join([level.get("title", "") for level in over_100]))[
            :900
        ]  # 900 character limit

        _ = embed.add_field(
            name="Over 100 Days",
            value=level_names,
            inline=False,
        )

    if len(levels) > 0:
        _ = embed.add_field(
            name="Newest", value=levels[-1].get("title", ""), inline=False
        )

    embeds.append(embed)

    return embeds


def beaten_unbeaten_embeds(levels: list[BeatenUnbeaten]) -> list[Embed]:
    embeds: list[Embed] = []

    for beaten in levels:
        title: str = beaten["title"]
        url: str = beaten["url"]
        color: int = beaten["color"]
        user: str = beaten["user"]
        time: str = beaten["time"]
        days: int = beaten["days"]
        extra: str = beaten["extra"]

        description: str = f"Beaten by {user} in {time} after {days} days!{extra}"

        embed: Embed = make_embed(title, description, url, color)
        embeds.append(embed)

    return embeds


def challenge_records_embeds(
    levels: list[utils.Level], old_levels: list[utils.Level]
) -> list[Embed]:
    embeds: list[Embed] = []

    # existing challenge maps
    challenge_maps: list[tuple[utils.Level, utils.Level]] = [
        (map, map_old)
        for map in levels
        for map_old in old_levels
        if map["identifier"] == map_old["identifier"]
        and "curated_challenge" in map.get("list_key", "")
    ]

    for map, map_old in challenge_maps:
        leaderboard: list[utils.Placement] = map.get("leaderboard", [])
        leaderboard_old: list[utils.Placement] = map_old.get("leaderboard", [])

        record: utils.Placement | None = (
            leaderboard[0] if len(leaderboard) > 0 else None
        )
        record_old: utils.Placement | None = (
            leaderboard_old[0] if len(leaderboard_old) > 0 else None
        )

        # no records just in case
        if record is None and record_old is None:
            continue

        title: str = map.get("title", "")
        identifier: str = map["identifier"]
        url: str = f"{utils.VIEWER_URL}?level={identifier}"
        description: str = ""
        color: int = utils.Colors.RED

        # old record and new record -> new record
        if (
            record is not None
            and record_old is not None
            and record["timestamp"] != record_old["timestamp"]
        ):
            description = f"New record by {record['user_name']}: {record["best_time"]}s"

        # old record and same record -> do nothing
        elif record is not None and record_old is not None:
            continue

        # only new record -> new record
        elif record is not None and record_old is None:
            description = f"New record by {record['user_name']}: {record["best_time"]}s"

        # only old record -> removed
        elif record_old is not None:
            description = "Record removed by moderator"
            color = utils.Colors.DARK_RED

        embed: Embed = make_embed(title, description, url, color)
        embeds.append(embed)

    return embeds


def challenge_updates_embeds(
    levels: list[utils.Level], old_levels: list[utils.Level]
) -> list[Embed]:
    embeds: list[Embed] = []

    # id maps
    old_by_id: dict[str, utils.Level] = {
        level["identifier"]: level
        for level in old_levels
        if "curated_challenge" in level.get("list_key", "")
    }
    new_by_id: dict[str, utils.Level] = {
        level["identifier"]: level
        for level in levels
        if "curated_challenge" in level.get("list_key", "")
    }

    # separate added and removed
    old_ids = old_by_id.keys()
    new_ids = new_by_id.keys()

    added_ids: set[str] = new_ids - old_ids
    removed_ids: set[str] = old_ids - new_ids

    # merge with added/removed flag
    different: list[tuple[utils.Level, bool]] = [
        (new_by_id[i], True) for i in added_ids
    ] + [(old_by_id[i], False) for i in removed_ids]

    # embed for each changed map
    for level, added in different:
        title: str = level.get("title", "")
        identifier: str = level["identifier"]
        description: str = (
            "Map added to a challenge" if added else "Map removed from a challenge"
        )
        url: str = f"{utils.VIEWER_URL}?level={identifier}"
        color: int = utils.Colors.DARK_RED

        embed: Embed = make_embed(title, description, url, color)
        embeds.append(embed)

    return embeds


def record_logs_embeds(
    levels: list[utils.Level], old_levels: list[utils.Level]
) -> list[Embed]:
    embeds: list[Embed] = []

    class NewRecord(TypedDict):
        identifier: str
        title: str
        record: utils.Placement

    for map in levels:
        # log top 100 for a challenge and top 10 for others
        limit: int = 100 if "curated_challenge" in map.get("list_key", "") else 10

        leaderboard: list[utils.Placement] = map.get("leaderboard", [])

        new_records: list[NewRecord] = []
        for i in range(min(len(leaderboard), limit)):
            identifier = leaderboard[i]["user_id"]
            for map_old in old_levels:
                old_leaderboard: list[utils.Placement] = map_old.get("leaderboard", [])
                if map["identifier"] == map_old["identifier"]:
                    found = False
                    for j in range(min(len(old_leaderboard), limit)):
                        if old_leaderboard[j]["user_id"] == identifier:
                            found = True
                            if (
                                leaderboard[i]["timestamp"]
                                != old_leaderboard[j]["timestamp"]
                            ):
                                new_records.append(
                                    {
                                        "identifier": map["identifier"],
                                        "title": map.get("title", ""),
                                        "record": leaderboard[i],
                                    }
                                )
                    if not found:
                        new_records.append(
                            {
                                "identifier": map["identifier"],
                                "title": map.get("title", ""),
                                "record": leaderboard[i],
                            }
                        )

        # record logs
        for entry in new_records:
            embed: Embed = Embed(
                title=entry["title"],
                url=f"{utils.VIEWER_URL}?level={entry['identifier']}",
                color=(
                    utils.Colors.RED
                    if int(entry["record"]["position"]) == 0
                    else utils.Colors.DARK_RED
                ),
            )
            _ = embed.add_field(
                name=entry["record"]["user_name"],
                value=f"{entry["record"]["position"]}: {entry["record"]['best_time']}s",
                inline=False,
            )
            embeds.append(embed)

    return embeds


def build_embeds(
    unbeaten_levels: list[utils.Level],
    beaten_unbeaten_levels: list[BeatenUnbeaten],
    best_of_grab_levels_old: list[utils.Level],
    best_of_grab_levels: list[utils.Level],
) -> dict[int, list[Embed]]:
    # merge embeds for each channel
    embeds: dict[int, list[Embed]] = {
        utils.Discord.Channels.UNBEATEN_LEVELS_UPDATES: [
            *unbeaten_levels_embeds(unbeaten_levels),
            *beaten_unbeaten_embeds(beaten_unbeaten_levels),
        ],
        utils.Discord.Channels.CHALLENGE_UPDATES: [
            *challenge_records_embeds(best_of_grab_levels, best_of_grab_levels_old),
            *challenge_updates_embeds(best_of_grab_levels, best_of_grab_levels_old),
        ],
        utils.Discord.Channels.RECORDS_LOGS: [
            *record_logs_embeds(best_of_grab_levels, best_of_grab_levels_old),
        ],
    }

    return embeds


def run_bot(embeds: dict[int, list[Embed]]) -> None:
    # setup bot
    bot: commands.Bot = commands.Bot(
        command_prefix="!",
        intents=discord.Intents.default(),
        allowed_mentions=discord.AllowedMentions(
            roles=True, users=False, everyone=False
        ),
    )

    @bot.event
    async def on_ready() -> None:  # pyright: ignore[reportUnusedFunction]
        # guild handles
        guild: Guild | None = bot.get_guild(utils.Discord.GUILD)
        if not guild:
            return

        unbeaten_levels_updates_channel: (
            GuildChannel | Thread | PrivateChannel | None
        ) = bot.get_channel(
            utils.Discord.Channels.UNBEATEN_LEVELS_UPDATES,
        )
        if not unbeaten_levels_updates_channel:
            return

        hardest_levels_role: Role | None = guild.get_role(
            utils.Discord.Roles.HARDEST_LEVELS,
        )

        # send ping
        ping: str = hardest_levels_role.mention if hardest_levels_role else ""
        if isinstance(unbeaten_levels_updates_channel, Messageable):
            _ = await unbeaten_levels_updates_channel.send(f"||{ping}||")

        # send embeds
        for channel_id, channel_embeds in embeds.items():
            channel: GuildChannel | Thread | PrivateChannel | None = bot.get_channel(
                channel_id
            )
            if not channel:
                continue

            for embed in channel_embeds:
                if isinstance(channel, Messageable):
                    _ = await channel.send(embed=embed)

        # close
        await bot.close()

    bot.run(BOT_TOKEN)


def main() -> None:
    # read required previous data
    most_plays_old: dict[str, MostPlays] = utils.read_data("most_plays")
    most_verified_old: dict[str, MostVerified] = utils.read_data("most_verified")
    unbeaten_levels_old: list[utils.Level] = utils.read_data("unbeaten_levels")
    all_verified_old: list[utils.Level] = utils.read_data("all_verified")
    best_of_grab_levels_old: list[utils.Level] = utils.read_data("best_of_grab")

    # run requests and data processing
    all_verified: list[utils.Level] = get_all_verified()

    add_trending_info(all_verified, all_verified_old)

    unbeaten_levels: list[utils.Level] = get_unbeaten(all_verified)
    hardest_levels_list = get_hardest_levels_list()
    best_of_grab_levels: list[utils.Level] = get_best_of_grab()
    most_verified: dict[str, MostVerified] = get_most_verified(
        all_verified, most_verified_old
    )
    most_plays: dict[str, MostPlays] = get_most_plays(all_verified, most_plays_old)
    total_levels: dict[str, int] = get_total_levels()

    beaten_unbeaten_levels: list[BeatenUnbeaten] = get_beaten_unbeaten(
        unbeaten_levels_old
    )

    # save new data
    utils.write_data(all_verified, "all_verified")
    utils.write_data(best_of_grab_levels, "best_of_grab")
    utils.write_data(unbeaten_levels, "unbeaten_levels")
    utils.write_data(most_verified, "most_verified")
    utils.write_data(most_plays, "most_plays")
    utils.write_data(hardest_levels_list, "hardest_levels_list")
    utils.write_data(total_levels, "total_level_count")

    # get embeds
    embeds: dict[int, list[Embed]] = build_embeds(
        unbeaten_levels,
        beaten_unbeaten_levels,
        best_of_grab_levels_old,
        best_of_grab_levels,
    )

    # run announcements
    run_bot(embeds)


if __name__ == "__main__":
    main()
