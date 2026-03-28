import sys
import json
import utils
from concurrent.futures import ThreadPoolExecutor

server_token_headers = json.loads(sys.argv[1])


def get_level_leaderboard(identifier):
    level_path = identifier.replace(":", "/")
    url = f"{utils.SERVER_API}statistics_top_leaderboard/{level_path}"

    response = utils.safe_get(url, server_token_headers)
    data: list = utils.safe_json(response) or []

    length = len(data)
    print(f"{length} entries for {identifier}")

    return data


class Scope:
    def __init__(self):
        # rating -> user id -> {maps, user_name}
        self.difficulty_records = {rating: {} for rating in utils.RATINGS}
        # rating -> level count
        self.difficulty_lengths = {rating: 0 for rating in utils.RATINGS}
        # user id -> [record count, ['title|identifier'][], username]
        self.leaderboard = {}
        # {...level, leaderboard}[]
        self.sole_victors = []
        # user id -> [finish count, username, total time]
        self.user_finishes = {}
        # user id -> [username, firsts count]
        self.first_to_beat = {}
        # user id -> timestamp[]
        self.timestamps_data = {}
        # 'user id|latest|oldest'[]
        self.timestamps_data_result = []
        # user id -> [record count, ['title|identifier'][], username]
        self.sorted_leaderboard = {}


def process(level: dict, scope: Scope):
    identifier = level["identifier"]
    title = level.get("title", "")
    statistics = level.get("statistics", {})

    leaderboard_data = get_level_leaderboard(identifier)

    # ignore unbeaten maps
    length = len(leaderboard_data)
    if length == 0:
        return

    # add leaderboard to level data
    level["leaderboard"] = leaderboard_data

    # sole = only 1 record
    if length == 1:
        scope.sole_victors.append(level)

    # add record holder
    record_holder = leaderboard_data[0]["user_id"]
    if record_holder not in scope.leaderboard:
        scope.leaderboard[record_holder] = [0, [], leaderboard_data[0]["user_name"]]

    scope.leaderboard[record_holder][0] += 1
    scope.leaderboard[record_holder][1].append(
        [title + "|" + identifier]
    )  # TODO: why did i add the title here

    # difficulty
    difficulty_string = (
        statistics["difficulty_string"]
        if "difficulty_string" in statistics
        else "unrated"
    )
    scope.difficulty_lengths[difficulty_string] += 1

    # finishes
    for record in leaderboard_data:
        user_id = record["user_id"] if "user_id" in record else None
        timestamp = record["timestamp"] if "timestamp" in record else None

        if user_id is None:
            continue

        # timestamp data
        if timestamp is not None:
            timestamp_id = int(int(timestamp) / 100)
            if user_id not in scope.timestamps_data:
                scope.timestamps_data[user_id] = [timestamp_id]
            else:
                scope.timestamps_data[user_id].append(timestamp_id)

        # difficulty records
        diff_records = scope.difficulty_records[difficulty_string]
        if user_id not in diff_records:
            diff_records[user_id] = {
                "maps": 0,
                "user_name": record["user_name"],
            }
        diff_records[user_id]["maps"] += 1

    # first person to complete (in top 100)
    first_record = None
    first_timestamp = float("inf")  # wtf is this syntax

    # all user stats
    for record in leaderboard_data:
        current_timestamp = record["timestamp"]
        user_id = record["user_id"]

        if int(current_timestamp) < first_timestamp:
            first_timestamp = int(current_timestamp)
            first_record = record

        # total finishes
        if user_id not in scope.user_finishes:
            scope.user_finishes[user_id] = [0, record["user_name"], 0]
        scope.user_finishes[user_id][0] += 1

        try:
            scope.user_finishes[user_id][2] += (
                record["best_time"] if "best_time" in record else 0
            )
        except TypeError:  # FIXME: what caused this?
            print(scope.user_finishes[user_id])

    # first person to complete
    if first_record is not None:
        first_user_id = first_record["user_id"]
        first_user_name = first_record["user_name"]

        if first_user_id not in scope.first_to_beat:
            scope.first_to_beat[first_user_id] = [first_user_name, 0]
        scope.first_to_beat[first_user_id][1] += 1


def sanitize(scope: Scope):
    leaderboard = {
        user: scores for user, scores in scope.leaderboard.items() if scores[0] >= 10
    }
    scope.sorted_leaderboard = dict(
        sorted(leaderboard.items(), key=lambda x: x[1][0], reverse=True)
    )

    for difficulty in scope.difficulty_records:
        scope.difficulty_records[difficulty] = {
            user_key: records
            for user_key, records in scope.difficulty_records[difficulty].items()
            if records["maps"] >= 10
        }

        scope.difficulty_records[difficulty] = dict(
            sorted(
                scope.difficulty_records[difficulty].items(),
                key=lambda x: x[1]["maps"],
                reverse=True,
            )[:200]
        )

    timestamps_data_counts = [
        (len(timestamps), key) for key, timestamps in scope.timestamps_data.items()
    ]
    timestamps_data_counts.sort(key=lambda x: x[0], reverse=True)
    timestamps_data_keys = [key for _count, key in timestamps_data_counts[:1000]]
    timestamps_data_result = []

    for key in timestamps_data_keys:
        timestamps = scope.timestamps_data[key]
        if timestamps:
            highest = max(timestamps)
            lowest = min(timestamps)
            timestamps_data_result.append(f"{key}:{highest}:{lowest}")

    user_finishes = {
        key: [finishes[0], finishes[1], round(finishes[2], 2)]
        for key, finishes in scope.user_finishes.items()
        if finishes[0] >= 10
    }
    user_finishes = dict(
        sorted(user_finishes.items(), key=lambda x: x[1][0], reverse=True)[:200]
    )

    first_to_beat = {
        key: beats for key, beats in scope.first_to_beat.items() if beats[1] >= 10
    }
    first_to_beat = dict(
        sorted(first_to_beat.items(), key=lambda x: x[1][1], reverse=True)[:200]
    )


def main():
    scope = Scope()

    # read levels
    levels: list = utils.read_data("all_verified")

    # process all data
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process, level, scope) for level in levels]

        for future in futures:
            future.result()

    # clean up, sort, slice
    sanitize(scope)

    # write stats
    utils.write_data(scope.user_finishes, "user_finishes")
    utils.write_data(scope.sorted_leaderboard, "sorted_leaderboard_records")
    utils.write_data(scope.sole_victors, "sole_victors")
    utils.write_data(scope.difficulty_records, "difficulty_records")
    utils.write_data(scope.difficulty_lengths, "difficulty_lengths")
    utils.write_data(scope.first_to_beat, "first_to_beat")
    utils.write_data(scope.timestamps_data_result, "timestamps_data")


if __name__ == "__main__":
    main()
