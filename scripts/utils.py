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


def MakeStatistics() -> Statistics:
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


def MakeLevelStatistics() -> LevelStatistics:
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
    position: int
    timestamp: str
    user_id: str
    user_name: str
    is_verification: NotRequired[bool]
    replay_key: NotRequired[str]


class Images(TypedDict):
    thumb: NotRequired[dict[str, JSON]]
    full: NotRequired[dict[str, JSON]]


# level details from lists
class Level(TypedDict):
    identifier: str
    iteration: int
    data_key: str
    complexity: int
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
    sections: NotRequired[list["Section"]]


class LevelBrowser(TypedDict):
    title: str
    sections: list[Section]
    tags: list[str]


# api
SERVER_API = "https://api.slin.dev/grab/v1/"
IMAGES_API = "https://grab-images.slin.dev/"

# websites
WEBSITE_URL = "https://grab-tools.live/"
VIEWER_URL = "https://grabvr.quest/levels/viewer/"

# config
FORMAT_VERSION = 100

# maybe get from server at runtime
RATINGS = ["unrated", "easy", "medium", "hard", "veryhard", "impossible"]


# colors
class Colors:
    YELLOW = 0xFFAA00
    ORANGE = 0xFF7500
    RED = 0xFF0000
    DARK_RED = 0x990000
    WHITE = 0xFFFFFF
    CYAN = 0x00FFFF
    BLACK = 0x000000


# discord ids
class Discord:
    GUILD = 1048213818775437394

    class Channels:
        CHALLENGE_UPDATES = 1241943979751374868
        UNBEATEN_LEVELS_UPDATES = 1144060608937996359
        RECORDS_LOGS = 1333319489726713877


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


def safe_json(data: requests.Response | str | bytes | bytearray | None) -> Any | None:
    if not data:
        return None

    try:
        if isinstance(data, requests.Response):
            return data.json()
        else:
            return json.loads(data)

    except (ValueError, json.JSONDecodeError, AttributeError):
        print("JSON decode failed")
        return None
