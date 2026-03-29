import json
import time
from typing import Any, TypedDict

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


# statistics from level details
class LevelStatistics(TypedDict):
    total_played: int | None
    difficulty: float | None
    liked: float | None
    time: float | None
    difficulty_string: str | None


def MakeLevelStatistics() -> LevelStatistics:
    return {
        "total_played": 0,
        "difficulty": 1.0,
        "liked": 0.0,
        "time": 0.0,
        "difficulty_string": "unrated",
    }


# level details from lists
class Level(TypedDict):
    identifier: str
    iteration: int
    data_key: str
    complexity: int
    title: str | None
    description: str | None
    creators: list[str] | None
    tags: list[str] | None
    verification_time: float | None
    curated_listings: list[str] | None
    format_version: int | None
    update_timestamp: int | None
    creation_timestamp: int | None
    statistics: LevelStatistics | None
    images: JSON


# user details
class User(TypedDict):
    user_id: str
    user_name: str | None
    is_admin: bool
    is_developer: bool
    is_supermoderator: bool
    is_moderator: bool
    is_verifier: bool
    is_creator: bool
    user_level_count: int
    grab_plus_active: bool
    active_customizations: JSON


# leaderboard placement entry
class Placement(TypedDict):
    best_time: float
    position: int
    timestamp: str
    user_id: str
    user_name: str
    is_verification: bool | None
    replay_key: str | None


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
        HARDEST_LIST_UPDATES = 1365172578242531379
        CHALLENGE_UPDATES = 1241943979751374868
        UNBEATEN_LEVELS_UPDATES = 1144060608937996359
        UNVERIFICATION_LOGS = 1238777601166934016
        RECORDS_LOGS = 1333319489726713877

    class Roles:
        HARDEST_LEVELS = 1077411286696087664


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
