from __future__ import annotations

import json
import time
from typing import Any, NotRequired, TypedDict

import requests

# types
type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None


# full statistics
class Statistics(TypedDict):
    level_identifier: str
    total_played_count: int
    total_finished_count: int
    played_count: int
    finished_count: int
    rated_count: int
    liked_count: int
    tipped_amount: int
    tipped_count: int
    average_time: float


def MakeStatistics() -> Statistics:  # noqa: N802
    return {
        "level_identifier": "",
        "total_played_count": 0,
        "total_finished_count": 1,  # default of 1 so its not couted as unbeaten
        "played_count": 25,
        "finished_count": 1,
        "rated_count": 0,
        "liked_count": 0,
        "tipped_amount": 0,
        "tipped_count": 0,
        "average_time": 0.0,
    }


# statistics from level details
class LevelStatistics(TypedDict):
    total_played: NotRequired[int]
    difficulty: NotRequired[float]
    liked: NotRequired[float]
    time: NotRequired[float]
    difficulty_string: NotRequired[str]


def MakeLevelStatistics() -> LevelStatistics:  # noqa: N802
    return {
        "total_played": 25,
        "difficulty": 1.0,
        "liked": 0.0,
        "time": 0.0,
        "difficulty_string": "unrated",
    }


# leaderboard placement entry
class Placement(TypedDict):
    best_time: float
    position: NotRequired[int]
    timestamp: str
    user_id: str
    user_name: str
    is_verification: NotRequired[bool]
    replay_key: NotRequired[str]


class Image(TypedDict):
    key: NotRequired[str]


class Images(TypedDict):
    thumb: NotRequired[Image]
    full: NotRequired[Image]


# level details from lists
class Level(TypedDict):
    identifier: str
    iteration: NotRequired[int]
    data_key: NotRequired[str]
    complexity: NotRequired[int]
    title: NotRequired[str]
    description: NotRequired[str]
    creators: NotRequired[list[str]]
    tags: NotRequired[list[str]]
    verification_time: NotRequired[float]
    curated_listings: NotRequired[list[str]]
    format_version: NotRequired[int]
    update_timestamp: NotRequired[int]
    creation_timestamp: NotRequired[int]
    statistics: NotRequired[LevelStatistics]
    images: NotRequired[Images]
    page_timestamp: NotRequired[str]
    list_key: NotRequired[str]
    leaderboard: NotRequired[list[Placement]]
    change: NotRequired[int]
    image_iteration: NotRequired[int]
    unbeaten: NotRequired[bool]


# user details
class User(TypedDict):
    user_id: str
    user_name: str
    is_admin: NotRequired[bool]
    is_developer: NotRequired[bool]
    is_supermoderator: NotRequired[bool]
    is_moderator: NotRequired[bool]
    is_verifier: NotRequired[bool]
    is_creator: NotRequired[bool]
    user_level_count: NotRequired[int]
    grab_plus_active: NotRequired[bool]
    active_customizations: NotRequired[JSON]


# level browser
class Section(TypedDict):
    title: NotRequired[str]
    title_short: NotRequired[str]
    list_key: NotRequired[str]
    image: NotRequired[str]
    font_size: NotRequired[int]
    type: NotRequired[str]
    size: NotRequired[int]
    sections: NotRequired[list[Section]]


class LevelBrowser(TypedDict):
    title: str
    sections: list[Section]
    tags: list[str]


# api
SERVER_API = "https://api.slin.dev/grab/v1/"
IMAGES_API = "https://grab-images.slin.dev/"

# websites
WEBSITE_URL = "https://grabvr.tools/"
VIEWER_URL = "https://grabvr.quest/levels/viewer/"

# config
FORMAT_VERSION = 100

# maybe get from server at runtime
RATINGS = ["unrated", "easy", "medium", "hard", "veryhard", "impossible"]


# colors
class Colors:
    YELLOW: int = 0xFFAA00
    ORANGE: int = 0xFF7500
    RED: int = 0xFF0000
    DARK_RED: int = 0x990000
    WHITE: int = 0xFFFFFF
    CYAN: int = 0x00FFFF
    BLACK: int = 0x000000


# discord ids
class Discord:
    GUILD: int = 1048213818775437394

    class Channels:
        CHALLENGE_UPDATES: int = 1241943979751374868
        UNBEATEN_LEVELS_UPDATES: int = 1144060608937996359
        RECORDS_LOGS: int = 1333319489726713877

        TESTING: int = 1269936084121419806


# json files
def write_data(data: Any, name: str) -> None:
    with open(f"data/{name}.json", "w") as file:
        json.dump(data, file)


def read_data(name: str) -> Any:
    with open(f"data/{name}.json") as file:
        data = json.load(file)

    return data


# safe functions
def safe_get(
    url: str, headers: dict[str, str] | None = None, attempts: int = 3
) -> requests.Response | None:
    timeout = 5
    delay = 1

    print(f"Request to {url}")

    for attempt in range(1, attempts + 1):
        try:
            response: requests.Response = requests.get(
                url, headers=headers or {}, timeout=timeout
            )
            response.raise_for_status()
            return response

        except requests.RequestException as e:
            if attempt == attempts:
                print(f"Request to {url} failed")
                return None

            print(f"Request to {url} attempt {attempt} failed: {e}")
            time.sleep(delay)

    return None


def safe_json(data: requests.Response | str | bytes | bytearray | None) -> Any | None:
    if not data:
        return None

    try:
        if isinstance(data, requests.Response):
            return data.json()

        return json.loads(data)

    except (ValueError, json.JSONDecodeError, AttributeError):
        print("JSON decode failed")
        return None


# data util
def pop(obj: Any, key: str) -> None:
    _ = obj.pop(key, None)


def pop_zero(obj: Any, key: str) -> None:
    if key in obj and obj[key] == 0:
        pop(obj, key)


def reduce_level(level: Level) -> None:
    # replace images with image_iteration
    if "images" in level:
        images = level["images"]
        if "thumb" in images:
            thumb = images["thumb"]
            if "key" in thumb:
                iteration = int(thumb["key"].split("_")[3])
                level["image_iteration"] = iteration

    # remove data key and override iteration
    if "data_key" in level:
        iteration = int(level["data_key"].split(":")[3])
        if iteration > 1:
            level["iteration"] = iteration

    # default values for statistics
    level["statistics"] = {**MakeLevelStatistics(), **level.get("statistics", {})}

    # remove unwanted keys
    pop(level, "verification_time")
    pop(level, "format_version")
    pop(level, "description")
    pop(level, "data_key")
    pop(level, "tags")
    pop(level, "images")
    pop(level, "page_timestamp")

    # leaderboard
    for placement in level.get("leaderboard", []):
        pop(placement, "replay_key")
        pop(placement, "position")

    # remove 0s
    pop_zero(level, "iteration")
    pop_zero(level, "change")
    pop_zero(level, "")
    pop_zero(level, "")
    pop_zero(level, "")
    pop_zero(level, "")

    statistics = level["statistics"]
    pop_zero(statistics, "total_played")
    pop_zero(statistics, "difficulty")
    pop_zero(statistics, "liked")
    pop_zero(statistics, "time")
