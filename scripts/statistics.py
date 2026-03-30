import sys
from concurrent.futures import ThreadPoolExecutor

from scripts.api import API
from scripts.utils import Level, Statistics, read_data, write_data

# api manager
server_auth: str = sys.argv[1]
api: API = API(server_auth)


class Scope:
    def __init__(self) -> None:
        # identifier -> statistics
        self.statistics: dict[str, Statistics] = {}


def process(level: Level, scope: Scope) -> None:
    identifier: str = level["identifier"]

    stats: Statistics | None = api.level_stats(identifier)
    if stats:
        scope.statistics[identifier] = stats


def sanitize(scope: Scope) -> None:
    for _key, value in scope.statistics.items():
        # remove redundant ids
        _ = value.pop("level_identifier", None)


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
    write_data(scope.statistics, "statistics")


if __name__ == "__main__":
    main()
