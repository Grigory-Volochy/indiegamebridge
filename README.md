# IndieGameBridge

A discovery platform connecting indie game developers with streamers.

Indie devs struggle to find the right small streamers to pitch their games to, and some streamers are systematically overlooked by big publisher creator programs. IndieGameBridge aggregates public streaming data into a filterable directory so both sides can find each other.

## Status

Early development. No usable build yet.

## Pipeline

- **Step #1:**
The backend\apps\fetch\management\commands\fetch_twitch_streams.py provides command 'fetch_twitch_streams'. The command is called via CRON every 20 minutes (VPS side setting - from real tests the poll usually takes 2-12 minutes, and seems to depend on the current load of Twitch's servers and the current number of live streams).
The script polls https://api.twitch.tv/helix/streams Twitch Helix API endpoint (each language is in a separate thread) and upserts streams which have non-empty game_id (streams with empty game_id are considered offtopic for the project and are not saved in the database).
After the streams polling, the script checks for stale streams (see _finalize_offline_streams()) and updates their status to offline if they have more than 1 snapshot and have at least 3 max viewers in any snapshot (all streams with only 1 snapshot or with max viewers less than 3 are considered irrelevant for the project and are removed from the database). For all streams which are turning offline, the script upserts Game (at this point a placeholder with only host_game_id populated) with default category 'new' if no Game row for that id exists yet.

- **Step #2:**
The backend\apps\fetch\management\commands\categorize_games.py provides command 'categorize_games'. The command is called via CRON every 20 minutes but with a 12-15 minute offset from the 'fetch_twitch_streams' CRON task, to avoid contention on Helix API rate limits and to spread VPS resource usage.
The script polls https://api.twitch.tv/helix/games Twitch Helix API endpoint for all the 'new' Games currently stored in the database. For those games which have non-empty 'igdb_id' field in the API response, the script updates category to 'isgame' and updates their 'name'. For those games which have empty 'igdb_id' field in the API response, the script updates category to 'isnongame' and updates their 'name'. The script stores both game and non-game Games for further usage (future streams may use the same game_id(s)).
It is expected that only the first runs will take up to a few minutes, while further runs will take less than a minute as new 'isgame' and 'isnongame' Games will appear rarely (a few thousand Games at the start and up to a few dozens or hundreds later).

- **Step #3:**
The backend\apps\fetch\management\commands\approve_streams.py provides command 'approve_streams'. The command is called with a few minutes offset from the latest run of 'categorize_games', at a 20 minute interval.
This script does not call any API and only decides whether to update the status of streams from 'offline' to 'approved' or remove the streams as irrelevant for the project (or keeps them as 'offline' if a stream contains at least one uncategorized game, e.g. 'new', and returns to such streams later).

- **Step #4:**
The backend\apps\fetch\management\commands\enrich_igdb_games.py provides command 'enrich_igdb_games'. The command has low priority and can be called at a higher interval than 20 minutes. The command only polls the IGDB API to add more detail to stored Games with the 'isgame' category. Can be called once per hour or less frequently. The frontend should handle both enriched and not-yet-enriched Games gracefully. The enrichment data has secondary value for the project (URLs to the source game page on IGDB, game description, etc).

## Tech Stack

- **Backend:**
Python, Django, PostgreSQL

- **Data sources:**
Twitch Helix API: https://dev.twitch.tv/docs/api/reference/
IGDB API: https://api-docs.igdb.com/
additional platforms under consideration

## License

[MIT](LICENSE)