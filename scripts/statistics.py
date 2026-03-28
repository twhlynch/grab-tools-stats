import sys
import json
import utils
from concurrent.futures import ThreadPoolExecutor

server_token_headers = json.loads(sys.argv[1])


def get_level_stats(level_identifier: str):
    level_path = level_identifier.replace(":", "/")
    url = f"{utils.SERVER_API}statistics/{level_path}"

    response = utils.safe_get(url, server_token_headers)
    data = utils.safe_json(response)

    return data


class Scope:
    def __init__(self):
        # identifier -> statistics
        self.statistics: dict[str, dict] = {}


def process(level: dict, scope: Scope):
    identifier: str = level["identifier"]

    stats = get_level_stats(identifier)
    if stats:
        scope.statistics[identifier] = stats


def sanitize(scope: Scope):
    for _key, value in scope.statistics.items():
        # remove redundant ids
        value.pop("level_identifier", None)


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
    utils.write_data(scope.statistics, "statistics")


if __name__ == "__main__":
    main()
