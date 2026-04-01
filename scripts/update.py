import math
import sys
from datetime import datetime, timedelta
from typing import NotRequired, TypedDict

from api import API
from discord import AllowedMentions, Embed, Intents, Thread
from discord.abc import GuildChannel, Messageable, PrivateChannel
from discord.ext import commands
from utils import (
    VIEWER_URL,
    WEBSITE_URL,
    Colors,
    Discord,
    Level,
    LevelBrowser,
    LevelStatistics,
    MakeLevelStatistics,
    MakeStatistics,
    Placement,
    Section,
    Statistics,
    User,
    read_data,
    write_data,
)

# api manager
server_auth: str = sys.argv[1]
api: API = API(server_auth)

bot_token: str | None = sys.argv[2] if len(sys.argv) > 2 else None


def filter_level(level: Level) -> None:
    # remove tags leaving "ok"
    if "tags" in level:
        if "ok" in level["tags"]:
            level["tags"] = ["ok"]
        else:
            del level["tags"]

    # remove most of the images data
    if "images" in level:
        if "full" in level["images"]:
            del level["images"]["full"]
        if "thumb" in level["images"]:
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
    level["statistics"] = {**MakeLevelStatistics(), **level.get("statistics", {})}

    # for some reason pyright is fine with removing required keys
    _ = level.pop("verification_time", None)
    _ = level.pop("format_version", None)
    _ = level.pop("description", None)
    _ = level.pop("data_key", None)


def filter_level_list(levels: list[Level]) -> None:
    for level in levels:
        filter_level(level)


def get_level_list(list_type: str) -> list[Level]:
    levels: list[Level] = api.level_list(list_type) or []

    filter_level_list(levels)
    return levels


def get_level_browser() -> LevelBrowser:
    data: LevelBrowser | None = api.browser()

    # this is required
    if data is None:
        sys.exit(0)

    return data


def get_user_name(
    creators: list[dict[str, str]],
    user_id: str,
    potential_name: str,
    priority: bool = False,
) -> str:

    for creator in creators:
        if creator["list_key"].split(":")[1] == user_id:
            return creator["title"]

    if priority:
        user_data: User | None = api.user_info(user_id)
        if user_data:
            return user_data["user_name"]

    return f"{potential_name}?"


def timestamp_to_days(timestamp: int, now: float | None = None) -> int:
    now = now or datetime.now().timestamp() * 1000

    days: int = math.floor((now - timestamp) / 1000 / 60 / 60 / 24)

    return days


def get_all_verified() -> list[Level]:
    verified: list[Level] | None = api.full_level_list("ok")

    if verified is None:
        sys.exit(0)  # required

    filter_level_list(verified)
    return verified


def find_list_keys(data: Section) -> list[str]:
    list_keys: list[str] = []

    title: str | None = data.get("title")
    list_key: str | None = data.get("list_key")

    if title in ["Past Competitions", "Weekly Spotlight"]:
        return list_keys  # empty

    if list_key is None or list_key.startswith("curated_gab"):
        return list_keys  # empty

    list_keys.append(list_key)

    for section in data.get("sections", []):
        list_keys.extend(find_list_keys(section))

    return list_keys


def get_best_of_grab() -> list[Level]:
    level_browser: LevelBrowser = get_level_browser()
    all_list_keys: list[str] = [
        key for section in level_browser["sections"] for key in find_list_keys(section)
    ]

    levels: list[Level] = []

    for list_key in all_list_keys:
        if list_key.startswith("curated_"):
            levels_list: list[Level] = get_level_list(list_key)
            for level in levels_list:
                level["list_key"] = list_key
                leaderboard: list[Placement] = (
                    api.level_leaderboard(level["identifier"]) or []
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


def get_unbeaten(levels: list[Level]) -> list[Level]:
    unbeaten: list[Level] = []

    impossible: list[Level] = api.full_level_list("ok_newest_impossible") or []
    impossible_map: dict[str, Level] = {
        level["identifier"]: level for level in impossible
    }  # TODO: maybe replace all this with the impossible list

    for level in levels:
        identifier: str = level["identifier"]

        # impossible -> unbeaten
        if identifier in impossible_map:
            unbeaten.append(level)
            continue

        timestamp: int = level.get("creation_timestamp", 0)
        days_old: int = timestamp_to_days(timestamp)

        statistics: LevelStatistics = level.get("statistics") or MakeLevelStatistics()

        difficulty: float = statistics.get("difficulty", 1.0)
        total_played: int = statistics.get("total_played", 0)
        difficulty_string: str = statistics.get("difficulty_string", "unrated")

        enough_data: bool = (days_old >= 1 and total_played > 300) or days_old >= 10

        if difficulty == 0 and difficulty_string == "impossible" and enough_data:
            # get full stats
            stats: Statistics = api.level_stats(identifier) or MakeStatistics()

            finished_count: int = stats["finished_count"]

            # no finishes -> unbeaten
            if finished_count == 0:
                unbeaten.append(level)
                continue

            if finished_count == 1:
                # get leaderboard
                leaderboard: list[Placement] = api.level_leaderboard(identifier) or []

                # no records -> unbeaten
                if len(leaderboard) == 0:
                    unbeaten.append(level)
                    continue

                first_entry: Placement = leaderboard[0]
                creator_id: str = identifier.split(":")[0]
                first_id: str = first_entry["user_id"]
                # only creator -> not unbeaten
                if first_id == creator_id:
                    continue

                # verification -> not unbeaten
                if first_entry.get("is_verification", False):
                    continue

                # unbeaten
                unbeaten.append(level)

    return unbeaten[::-1]  # old to new order


class MostVerified(TypedDict):
    count: int
    user_name: NotRequired[str]
    levels: NotRequired[int]
    change: NotRequired[int]


def get_most_verified(
    levels: list[Level],
    old_levels: dict[str, MostVerified],
    featured_creators: list[dict[str, str]],
) -> dict[str, MostVerified]:
    verified_counts: dict[str, MostVerified] = {}

    # sum user_id -> level count
    for level in levels:
        user_id: str = level["identifier"].split(":")[0]
        if user_id not in verified_counts:
            verified_counts[user_id] = {"count": 0}

        verified_counts[user_id]["count"] += 1

    # sort by count descending
    sorted_list: list[tuple[str, MostVerified]] = sorted(
        verified_counts.items(), key=lambda x: x[1]["count"], reverse=True
    )

    # top 0 - 10
    most_verified: dict[str, MostVerified] = dict(sorted_list[:10])
    # top 10 - 200
    potentials: dict[str, MostVerified] = dict(sorted_list[10:][:190])

    # add username and level count to entries
    for user_id, data in most_verified.items():
        user_data: User | None = api.user_info(user_id)
        if user_data:
            data["user_name"] = user_data["user_name"]
            data["levels"] = user_data.get("user_level_count", 0)

    # try to add username without making request
    for user_id, potential in potentials.items():
        for level in levels:
            if user_id == level["identifier"].split(":")[0]:
                potential_name = ""
                if "creators" in level:
                    potential_name: str = level["creators"][0]
                potential["user_name"] = get_user_name(
                    featured_creators, user_id, potential_name
                )
                break
        # use count as levels
        potential["levels"] = potential["count"]

    # combine with potentials
    most_verified |= potentials

    # add change if possible
    for user_id in most_verified:
        if user_id in old_levels:
            most_verified[user_id]["change"] = (
                most_verified[user_id]["count"] - old_levels[user_id]["count"]
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
    levels: list[Level],
    old_levels: dict[str, MostPlays],
    featured_creators: list[dict[str, str]],
) -> dict[str, MostPlays]:
    plays_counts: dict[str, MostPlays] = {}

    # sum user_id -> level count, plays total
    for level in levels:
        user_id: str = level["identifier"].split(":")[0]
        if user_id not in plays_counts:
            plays_counts[user_id] = {"plays": 0, "count": 0}

        statistics: LevelStatistics = level.get("statistics", MakeLevelStatistics())
        plays_counts[user_id]["plays"] += statistics.get("total_played", 0)
        plays_counts[user_id]["count"] += 1

    # sort by plays descending
    sorted_list: list[tuple[str, MostPlays]] = sorted(
        plays_counts.items(), key=lambda x: x[1]["plays"], reverse=True
    )

    # top 0 - 10
    most_plays: dict[str, MostPlays] = dict(sorted_list[:10])
    # top 10 - 200
    potentials: dict[str, MostPlays] = dict(sorted_list[10:][:190])

    # add username and level count to entries
    for user_id, data in most_plays.items():
        user_data: User | None = api.user_info(user_id)
        if user_data:
            data["user_name"] = user_data["user_name"]
            data["levels"] = user_data.get("user_level_count", 0)

    # try to add username without making request
    for user_id, potential in potentials.items():
        for level in levels:
            if user_id == level["identifier"].split(":")[0]:
                potential_name = ""
                if "creators" in level:
                    potential_name: str = level["creators"][0]
                potential["user_name"] = get_user_name(
                    featured_creators, user_id, potential_name
                )
                break
        # use count as levels
        potential["levels"] = potential["count"]

    # combine with potentials
    most_plays |= potentials

    # add change if possible
    for user_id in most_plays:
        if user_id in old_levels:
            most_plays[user_id]["change"] = (
                most_plays[user_id]["plays"] - old_levels[user_id]["plays"]
            )
        else:
            most_plays[user_id]["change"] = 0

    return most_plays


def add_trending_info(all_verified: list[Level], old_data: list[Level]) -> None:
    for level in all_verified:
        # find old level
        old_level: Level | None = None
        for old_level_i in old_data:
            if level["identifier"] == old_level_i["identifier"]:
                old_level = old_level_i
                break

        statistics: LevelStatistics = level.get("statistics", MakeLevelStatistics())

        # calculate change
        if old_level:
            old_statistics: LevelStatistics = old_level.get(
                "statistics", MakeLevelStatistics()
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


def get_beaten_unbeaten(
    levels_old: list[Level], levels: list[Level]
) -> list[BeatenUnbeaten]:
    beaten: list[BeatenUnbeaten] = []

    levels_map: dict[str, Level] = {level["identifier"]: level for level in levels}

    for old_level in levels_old:
        identifier: str = old_level["identifier"]

        # still unbeaten -> not beaten
        if identifier in levels_map:
            continue

        leaderboard: list[Placement] = api.level_leaderboard(identifier) or []

        # empty leaderboard -> not beaten
        if len(leaderboard) == 0:
            continue

        title: str = old_level.get("title", "")
        creation_timestamp: int = old_level.get("creation_timestamp", 0)
        update_timestamp: int = old_level.get("update_timestamp", 0)

        creation_days: int = timestamp_to_days(creation_timestamp)
        update_days: int = timestamp_to_days(update_timestamp)

        # get oldest record
        victor: Placement = min(leaderboard, key=lambda x: x["timestamp"])

        url: str = f"{VIEWER_URL}?level={old_level['identifier']}"
        time: str = str(timedelta(seconds=victor["best_time"]))
        user: str = victor["user_name"]

        extra: str = (
            f" ({creation_days} since creation)"
            if update_timestamp != creation_timestamp
            else ""
        )

        # color based on age
        color = Colors.YELLOW
        if update_days >= 100:
            color = Colors.ORANGE
        if update_days >= 365:
            color = Colors.RED
        if update_days >= 1000:
            color = Colors.WHITE

        item: BeatenUnbeaten = {
            "title": title,
            "user": user,
            "time": time,
            "days": update_days,
            "url": url,
            "extra": extra,
            "color": color,
        }
        beaten.append(item)

    return beaten


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


def unbeaten_levels_embeds(levels: list[Level]) -> list[Embed]:
    embeds: list[Embed] = []

    if not levels:
        return embeds

    embed: Embed = make_embed(
        "Unbeaten Levels Update",
        "Unbeaten Update",
        f"{WEBSITE_URL}stats?tab=Unbeaten",
        Colors.CYAN,
    )

    _ = embed.add_field(name="Count", value=str(len(levels)))

    over_100: list[Level] = [
        level
        for level in levels
        if timestamp_to_days(level.get("update_timestamp", 0)) >= 100
    ]

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
    levels: list[Level], old_levels: list[Level]
) -> list[Embed]:
    embeds: list[Embed] = []

    # existing challenge levels
    challenge_levels: list[tuple[Level, Level]] = [
        (level, level_old)
        for level in levels
        for level_old in old_levels
        if level["identifier"] == level_old["identifier"]
        and "curated_challenge" in level.get("list_key", "")
    ]

    for level, level_old in challenge_levels:
        leaderboard: list[Placement] = level.get("leaderboard", [])
        leaderboard_old: list[Placement] = level_old.get("leaderboard", [])

        record: Placement | None = leaderboard[0] if len(leaderboard) > 0 else None
        record_old: Placement | None = (
            leaderboard_old[0] if len(leaderboard_old) > 0 else None
        )

        # no records just in case
        if record is None and record_old is None:
            continue

        title: str = level.get("title", "")
        identifier: str = level["identifier"]
        url: str = f"{VIEWER_URL}?level={identifier}"
        description: str = ""
        color: int = Colors.RED

        # old record and new record -> new record
        if (
            record is not None
            and record_old is not None
            and record["timestamp"] != record_old["timestamp"]
        ):
            description = f"New record by {record['user_name']}: {record['best_time']}s"

        # old record and same record -> do nothing
        elif record is not None and record_old is not None:
            continue

        # only new record -> new record
        elif record is not None and record_old is None:
            description = f"New record by {record['user_name']}: {record['best_time']}s"

        # only old record -> removed
        elif record_old is not None:
            description = "Record removed by moderator"
            color = Colors.DARK_RED

        embed: Embed = make_embed(title, description, url, color)
        embeds.append(embed)

    return embeds


def challenge_updates_embeds(
    levels: list[Level], old_levels: list[Level]
) -> list[Embed]:
    embeds: list[Embed] = []

    # id levels
    old_by_id: dict[str, Level] = {
        level["identifier"]: level
        for level in old_levels
        if "curated_challenge" in level.get("list_key", "")
    }
    new_by_id: dict[str, Level] = {
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
    different: list[tuple[Level, bool]] = [(new_by_id[i], True) for i in added_ids] + [
        (old_by_id[i], False) for i in removed_ids
    ]

    # embed for each changed level
    for level, added in different:
        title: str = level.get("title", "")
        identifier: str = level["identifier"]
        description: str = (
            "Level added to a challenge" if added else "Level removed from a challenge"
        )
        url: str = f"{VIEWER_URL}?level={identifier}"
        color: int = Colors.DARK_RED

        embed: Embed = make_embed(title, description, url, color)
        embeds.append(embed)

    return embeds


def record_logs_embeds(levels: list[Level], old_levels: list[Level]) -> list[Embed]:
    embeds: list[Embed] = []

    class NewRecord(TypedDict):
        identifier: str
        title: str
        record: Placement

    old_levels_map: dict[str, Level] = {
        level["identifier"]: level for level in old_levels
    }

    for level in levels:
        identifier: str = level["identifier"]
        title: str = level.get("title", "")

        # log top 100 for a challenge and top 10 for others
        limit: int = 100 if "curated_challenge" in level.get("list_key", "") else 10

        leaderboard: list[Placement] = level.get("leaderboard", [])[:limit]

        old_level: Level | None = old_levels_map.get(identifier)
        old_leaderboard: list[Placement] = (old_level or {}).get("leaderboard", [])[
            :limit
        ]

        old_records: dict[str, Placement] = {r["user_id"]: r for r in old_leaderboard}

        new_records: list[NewRecord] = []

        for record in leaderboard:
            user_id: str = record["user_id"]
            old_record: Placement | None = old_records.get(user_id)

            # new entry or updated timestamp
            if not old_record or record["timestamp"] != old_record["timestamp"]:
                new_records.append(
                    {
                        "identifier": identifier,
                        "title": title,
                        "record": record,
                    }
                )

        # build embeds
        for entry in new_records:
            record: Placement = entry["record"]

            l_id: str = entry["identifier"]
            url: str = f"{VIEWER_URL}?level={l_id}"
            color: int = Colors.RED if int(record["position"]) == 0 else Colors.DARK_RED

            name: str = record["user_name"]
            info: str = f"{record['position']}: {record['best_time']}s"

            embed: Embed = make_embed(entry["title"], "", url, color)
            _ = embed.add_field(name=name, value=info, inline=False)

            embeds.append(embed)

    return embeds


def build_embeds(
    unbeaten_levels: list[Level],
    beaten_unbeaten_levels: list[BeatenUnbeaten],
    best_of_grab_levels_old: list[Level],
    best_of_grab_levels: list[Level],
) -> dict[int, list[Embed]]:
    # merge embeds for each channel
    embeds: dict[int, list[Embed]] = {
        Discord.Channels.UNBEATEN_LEVELS_UPDATES: [
            *unbeaten_levels_embeds(unbeaten_levels),
            *beaten_unbeaten_embeds(beaten_unbeaten_levels),
        ],
        Discord.Channels.CHALLENGE_UPDATES: [
            *challenge_records_embeds(best_of_grab_levels, best_of_grab_levels_old),
            *challenge_updates_embeds(best_of_grab_levels, best_of_grab_levels_old),
        ],
        Discord.Channels.RECORDS_LOGS: [
            *record_logs_embeds(best_of_grab_levels, best_of_grab_levels_old),
        ],
    }

    return embeds


def run_bot(token: str, embeds: dict[int, list[Embed]]) -> None:
    # setup bot
    bot: commands.Bot = commands.Bot(
        command_prefix="!",
        intents=Intents.default(),
        allowed_mentions=AllowedMentions(roles=True, users=False, everyone=False),
    )

    @bot.event
    async def on_ready() -> None:  # pyright: ignore[reportUnusedFunction]
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

    bot.run(token)


def debug_embeds(embeds_map: dict[int, list[Embed]]) -> None:
    for key, embeds in embeds_map.items():
        print(f"Channel: <{key}>")

        for embed in embeds:
            print(f"Title: {embed.title}")
            print(f"  Description: {embed.description}")
            print(f"  URL: {embed.url}")
            print(f"  Colour: {embed.color}")

            if embed.fields:
                print("  Fields:")
                for field in embed.fields:
                    print(f"    {field.name}: {field.value} inline={field.inline}")

            print()  # newline


def main() -> None:
    # read required previous data
    most_plays_old: dict[str, MostPlays] = read_data("most_plays")
    most_verified_old: dict[str, MostVerified] = read_data("most_verified")
    unbeaten_levels_old: list[Level] = read_data("unbeaten_levels")
    all_verified_old: list[Level] = read_data("all_verified")
    best_of_grab_levels_old: list[Level] = read_data("best_of_grab")
    featured_creators: list[dict[str, str]] = read_data("featured_creators")

    # run requests and data processing
    all_verified: list[Level] = get_all_verified()

    add_trending_info(all_verified, all_verified_old)

    unbeaten_levels: list[Level] = get_unbeaten(all_verified)
    best_of_grab_levels: list[Level] = get_best_of_grab()
    most_verified: dict[str, MostVerified] = get_most_verified(
        all_verified, most_verified_old, featured_creators
    )
    most_plays: dict[str, MostPlays] = get_most_plays(
        all_verified, most_plays_old, featured_creators
    )
    total_levels: dict[str, int] = api.level_count()

    beaten_unbeaten_levels: list[BeatenUnbeaten] = get_beaten_unbeaten(
        unbeaten_levels_old,
        unbeaten_levels,
    )

    # save new data
    write_data(all_verified, "all_verified")
    write_data(best_of_grab_levels, "best_of_grab")
    write_data(unbeaten_levels, "unbeaten_levels")
    write_data(most_verified, "most_verified")
    write_data(most_plays, "most_plays")
    write_data(total_levels, "total_level_count")

    # get embeds
    embeds: dict[int, list[Embed]] = build_embeds(
        unbeaten_levels,
        beaten_unbeaten_levels,
        best_of_grab_levels_old,
        best_of_grab_levels,
    )

    # run announcements
    if bot_token:
        run_bot(bot_token, embeds)
    else:
        debug_embeds(embeds)


if __name__ == "__main__":
    main()
