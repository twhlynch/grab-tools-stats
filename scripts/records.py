import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict

from api import API
from utils import (
    RATINGS,
    Level,
    LevelStatistics,
    MakeLevelStatistics,
    Placement,
    read_data,
    write_data,
)

# api manager
server_auth: str = sys.argv[1]
api: API = API(server_auth)


class DifficultyRecord(TypedDict):
    levels: int
    user_name: str


class Scope:
    # fmt: off
    def __init__(self)-> None:
        # rating -> user id -> {levels, user_name}
        self.difficulty_records: dict[str, dict[str, DifficultyRecord]] = {rating: {} for rating in RATINGS}
        # rating -> level count
        self.difficulty_lengths: dict[str, int] = dict.fromkeys(RATINGS, 0)
        # user id -> [record count, identifier[], username]
        self.leaderboard: dict[str, list[int | list[str] | str]] = {} # TODO: these typed lists need to be replaced
        # {...level, leaderboard}[]
        self.sole_victors: list[Level] = []
        # user id -> [finish count, username, total time]
        self.user_finishes: dict[str, list[int | str | float]] = {}
        # user id -> timestamp[]
        self.timestamps_data: dict[str, list[int]] = {}
        # 'user id:latest:oldest'[]
        self.timestamps_data_result: list[str] = []
        # user id -> [record count, identifier[], username]
        self.sorted_leaderboard: dict[str, list[int | list[str] | str]] = {}


def process(level: Level, scope: Scope) -> None:
    identifier: str = level["identifier"]

    statistics: LevelStatistics = level.get("statistics") or MakeLevelStatistics()

    leaderboard_data: list[Placement] = api.level_leaderboard(identifier) or []

    # ignore unbeaten levels
    length: int = len(leaderboard_data)
    if length == 0:
        return

    # sole = only 1 record
    if length == 1:
        # add leaderboard to level data
        level["leaderboard"] = leaderboard_data
        # add sole record
        scope.sole_victors.append(level)

    # get record holder
    first_entry: Placement = leaderboard_data[0]
    record_user_name: str = first_entry["user_name"]
    record_user_id: str = first_entry["user_id"]

    # add record holder
    if record_user_id not in scope.leaderboard:
        scope.leaderboard[record_user_id] = [0, [], record_user_name]

    # accumulate stats
    scope.leaderboard[record_user_id][0] += 1
    scope.leaderboard[record_user_id][1].append(identifier)

    # difficulty
    difficulty_string: str = statistics.get("difficulty_string") or "unrated"
    scope.difficulty_lengths[difficulty_string] += 1

    # finishes
    for record in leaderboard_data:
        user_id: str = record["user_id"]
        user_name: str = record["user_name"]
        timestamp: str = record.get("timestamp")
        best_time: float = record.get("best_time") or 0.0  # can be null

        # timestamp data
        if timestamp:
            timestamp_id: int = int(timestamp) // 100
            if user_id not in scope.timestamps_data:
                scope.timestamps_data[user_id] = [timestamp_id]
            else:
                scope.timestamps_data[user_id].append(timestamp_id)

        # difficulty records
        diff_records: dict[str, DifficultyRecord] = scope.difficulty_records[
            difficulty_string
        ]
        if user_id not in diff_records:
            diff_records[user_id] = {
                "levels": 0,
                "user_name": user_name,
            }

        diff_records[user_id]["levels"] += 1

        # total finishes
        if user_id not in scope.user_finishes:
            scope.user_finishes[user_id] = [0, user_name, 0]

        scope.user_finishes[user_id][0] += 1
        scope.user_finishes[user_id][2] += best_time


def sanitize(scope: Scope) -> None:
    # users with more that 10 records
    scope.leaderboard = {k: v for k, v in scope.leaderboard.items() if v[0] >= 10}
    # sort by records descending
    scope.sorted_leaderboard = dict(
        sorted(scope.leaderboard.items(), key=lambda x: x[1][0], reverse=True)
    )

    for difficulty in scope.difficulty_records:
        # users with more than 10 records
        scope.difficulty_records[difficulty] = {
            k: v
            for k, v in scope.difficulty_records[difficulty].items()
            if v["levels"] >= 10
        }
        # sort by records descending top 200
        scope.difficulty_records[difficulty] = dict(
            sorted(
                scope.difficulty_records[difficulty].items(),
                key=lambda x: x[1]["levels"],
                reverse=True,
            )[:200]
        )

    # timestamp count for each user
    timestamps_data_counts: list[tuple[int, str]] = [
        (len(timestamps), key) for key, timestamps in scope.timestamps_data.items()
    ]
    # sort by most timestamps
    timestamps_data_counts.sort(key=lambda x: x[0], reverse=True)
    # user ids for top 1000 in num timestamps
    timestamps_data_keys: list[str] = [
        key for _count, key in timestamps_data_counts[:1000]
    ]
    # key, min, max for each user
    scope.timestamps_data_result = [
        f"{key}:{max(timestamps)}:{min(timestamps)}"
        for key in timestamps_data_keys
        if (timestamps := scope.timestamps_data[key])
    ]

    # users with more than 10 finishes
    scope.user_finishes = {
        key: [finishes[0], finishes[1], round(finishes[2], 2)]
        for key, finishes in scope.user_finishes.items()
        if finishes[0] >= 10
    }
    # sort by finishes descending top 200
    scope.user_finishes = dict(
        sorted(scope.user_finishes.items(), key=lambda x: x[1][0], reverse=True)[:200]
    )


def main() -> None:
    scope = Scope()

    # read levels
    levels: list[Level] = read_data("all_verified")

    # process all data
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process, level, scope) for level in levels]

        for future in futures:
            future.result()

    # clean up, sort, slice
    sanitize(scope)

    # write stats
    write_data(scope.user_finishes, "user_finishes")
    write_data(scope.sorted_leaderboard, "sorted_leaderboard_records")
    write_data(scope.sole_victors, "sole_victors")
    write_data(scope.difficulty_records, "difficulty_records")
    write_data(scope.difficulty_lengths, "difficulty_lengths")
    write_data(scope.timestamps_data_result, "timestamps_data")


if __name__ == "__main__":
    main()
