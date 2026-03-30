# grab-tools-stats

Stats scraping scripts and api for Grab Tools

## Data

### general

all_verified - `Level[]`

best_of_grab - `Level[]`

unbeaten_levels - `Level[]`

most_verified - `user_id -> {count, user_name, levels, change}`

most_plays - `user_id -> {plays, count, user_name, levels, change}`

total_level_count - `{levels}`

### statistics

statistics - `level_id -> Statistics`

### records

user_finishes - `user_id -> [finish_count, user_name, total_time]`

sorted_leaderboard_records - `user_id -> [record_count, identifier[], user_name]`

sole_victors - `{...Level, leaderboard}[]`

difficulty_records - `rating -> user id -> {levels, user_name}`

difficulty_lengths - `rating -> level_count`

timestamps_data - `user_id:latest:oldest[]`
