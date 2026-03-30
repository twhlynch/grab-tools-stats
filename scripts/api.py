import json

import requests

from scripts.utils import (
    FORMAT_VERSION,
    SERVER_API,
    Level,
    LevelBrowser,
    Placement,
    Statistics,
    User,
    safe_get,
    safe_json,
)


class API:
    def __init__(self, server_auth: str) -> None:
        self.auth = json.loads(server_auth)

    def identifier_path(self, identifier: str) -> str:
        return identifier.replace(":", "/")

    # endpoints

    def level_leaderboard(self, identifier: str) -> list[Placement] | None:
        level_path: str = self.identifier_path(identifier)
        url: str = f"{SERVER_API}statistics_top_leaderboard/{level_path}"

        response: requests.Response | None = safe_get(url, self.auth)
        data: list[Placement] | None = safe_json(response)

        return data

    def level_stats(self, identifier: str) -> Statistics | None:
        level_path: str = self.identifier_path(identifier)
        url: str = f"{SERVER_API}statistics/{level_path}"

        response: requests.Response | None = safe_get(url, self.auth)
        data: Statistics | None = safe_json(response)

        return data

    def browser(self) -> LevelBrowser | None:
        url: str = f"{SERVER_API}get_level_browser?version=1"

        response: requests.Response | None = safe_get(url, headers=self.auth)
        data: LevelBrowser | None = safe_json(response)

        return data

    def level_list(self, type: str) -> list[Level] | None:
        url: str = f"{SERVER_API}list?max_format_version={FORMAT_VERSION}&type={type}"

        response: requests.Response | None = safe_get(url, headers=self.auth)
        levels: list[Level] | None = safe_json(response)

        return levels

    def user_info(self, user_id: str) -> User | None:
        url: str = f"{SERVER_API}get_user_info?user_id={user_id}"

        response: requests.Response | None = safe_get(url, headers=self.auth)
        data: User | None = safe_json(response)

        return data

    def level_count(self) -> dict[str, int]:
        url: str = f"{SERVER_API}total_level_count?type=newest"

        response: requests.Response | None = safe_get(url, headers=self.auth)

        count: int = int(response.text if response else 0)

        return {"levels": count}

    def full_level_list(self, type: str) -> list[Level] | None:
        levels: list[Level] = []

        page_timestamp: str = ""

        while True:
            url: str = (
                f"{SERVER_API}list?max_format_version={FORMAT_VERSION}&type={type}&page_timestamp={page_timestamp}"
            )

            response: requests.Response | None = safe_get(url, headers=self.auth)
            data: list[Level] | None = safe_json(response)

            if data is None:
                return None  # fail whole list

            # accumulate
            levels.extend(data)

            # get next page
            if len(data) > 0 and "page_timestamp" in data[-1]:
                page_timestamp = data[-1]["page_timestamp"]
            else:
                # no timestamp, end of list
                break

        return levels
