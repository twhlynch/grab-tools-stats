import json
import time

import requests

# type
type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

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
def write_data(data: JSON, name: str) -> None:
    with open(f"data/{name}.json", "w") as file:
        json.dump(data, file)


def read_data(name: str) -> JSON:
    with open(f"data/{name}.json") as file:
        data: JSON = json.load(file)

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


def safe_json(data: requests.Response | str | bytes | bytearray | None) -> JSON | None:
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
