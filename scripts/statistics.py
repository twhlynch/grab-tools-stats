import sys
import json
import utils

server_token_headers = json.loads(sys.argv[1])


def get_level_stats(level_identifier: str):
    level_path = level_identifier.replace(":", "/")
    url = f"{utils.SERVER_API}statistics/{level_path}"

    response = utils.safe_get(url, server_token_headers)
    data = utils.safe_json(response)

    return data


def main():
    statistics = {}

    # read levels
    levels: list = utils.read_data("all_verified")

    # get stats for levels
    for level in levels:
        identifier: str = level["identifier"]

        stats = get_level_stats(identifier)
        if stats:
            statistics[identifier] = stats

    # write stats
    utils.write_data(statistics, "statistics")


if __name__ == "__main__":
    main()
