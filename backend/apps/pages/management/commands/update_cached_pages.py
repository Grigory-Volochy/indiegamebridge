import logging

from django.contrib.postgres.aggregates import ArrayAgg
from django.core.management.base import BaseCommand
from django.db.models import Count, Max

from apps.streams.models import Game, GameGenre, Stream, StreamerProfile
from apps.pages.models import CachedPage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Recomputes pre-rendered page payloads stored in the CachedPage table."

    # Cap on rows in the home page search results.
    home_top_n = 10

    def handle(self, *args, **kwargs):
        logger.info("Updating cached pages...")
        self._update_home_page()
        logger.info("Cached pages update finished.")

    def _get_search_form_field(self, **kwargs):
        form_field = {
            "filter_type": "",
            "filter_name": "",
            "filter_label": "",
            "multi_values": [],
            "multi_default": [],
            "single_default": "",
            "min_values": [],
            "min_labels": [],
            "min_default": "",
            "max_values": [],
            "max_labels": [],
            "max_default": "",
        }
        for key, value in kwargs.items():
            form_field[key] = value
        return form_field
    
    def _get_quant_filter_values(self):
        return [
            {"v": "3", "l": "3"},
            {"v": "10", "l": "10"},
            {"v": "50", "l": "50"},
            {"v": "100", "l": "100"},
            {"v": "500", "l": "500"},
            {"v": "1000", "l": "1000"},
            {"v": "5000", "l": "5000"},
            {"v": "10000", "l": "10000"},
            {"v": "50000", "l": "50000"},
            {"v": "100000", "l": "100000"}
        ]

    def _get_time_filter_values(self):
        return [
            {"v": "20m", "l": "20 minutes"},
            {"v": "1h", "l": "1 Hour"},
            {"v": "2h", "l": "2 Hours"},
            {"v": "3h", "l": "3 Hours"},
            {"v": "6h", "l": "6 Hours"},
            {"v": "9h", "l": "9 Hours"},
            {"v": "12h", "l": "12 Hours"},
            {"v": "24h", "l": "24 Hours"}
        ]
    
    def _get_demo_search_results(self):
        # Streamers qualify if they have at least one APPROVED stream in English.
        # Aggregates run over all of their APPROVED streams (any language) so
        # totals reflect the streamer's full footprint, not just English ones.
        # Future ExcludedStreamers integration: add `.exclude(streamer_profile_id__in=excluded_ids)`
        # to the top_aggregates queryset before the slice.
        english_streamer_ids = (
            Stream.objects.filter(
                status=Stream.Status.APPROVED,
                language="en",
            )
            .values_list("streamer_profile_id", flat=True)
            .distinct()
        )

        top_aggregates = list(
            Stream.objects.filter(
                status=Stream.Status.APPROVED,
                streamer_profile_id__in=english_streamer_ids,
            )
            .values("streamer_profile_id")
            .annotate(
                tracked_streams=Count("id"),
                peak_viewers=Max("max_viewers"),
                languages=ArrayAgg("language", distinct=True),
            )
            .order_by("-peak_viewers", "-tracked_streams")[: self.home_top_n]
        )

        profile_ids = [row["streamer_profile_id"] for row in top_aggregates]
        profiles_by_id = {
            profile.id: profile
            for profile in StreamerProfile.objects.filter(id__in=profile_ids).only(
                "id", "host_login", "host_display_name"
            )
        }

        # Attach the 20 most recent APPROVED streams per top streamer. One small
        # query per streamer (10 total) is simpler than a window-function workaround
        # and trivial at this scale (hourly cache rebuild).
        streams_by_profile = {
            profile_id: list(
                Stream.objects.filter(
                    streamer_profile_id=profile_id,
                    status=Stream.Status.APPROVED,
                ).order_by("-finished_at")[:20]
            )
            for profile_id in profile_ids
        }

        # Resolve every referenced game in a single query.
        all_game_ids = {
            gid
            for streams in streams_by_profile.values()
            for stream in streams
            for gid in (stream.host_game_ids or [])
        }
        games_by_host_id = {
            game.host_game_id: game
            for game in Game.objects.filter(host_game_id__in=all_game_ids).only(
                "host_game_id", "host_name",
            )
        }

        search_results = []
        for row in top_aggregates:
            profile = profiles_by_id.get(row["streamer_profile_id"])
            if profile is None:
                continue

            streams_payload = []
            for stream in streams_by_profile.get(profile.id, []):
                games_payload = []
                for gid in (stream.host_game_ids or []):
                    game = games_by_host_id.get(gid)
                    if game is None:
                        continue
                    games_payload.append({
                        "host_game_id": game.host_game_id,
                        "host_name": game.host_name,
                    })
                streams_payload.append({
                    "host_stream_id": stream.host_stream_id,
                    "language": stream.language,
                    "max_viewers": stream.max_viewers,
                    "started_at": stream.started_at.isoformat(),
                    "finished_at": stream.finished_at.isoformat(),
                    "games": games_payload,
                })

            search_results.append({
                "display_name": profile.host_display_name,
                "login": profile.host_login,
                "twitch_url": f"https://twitch.tv/{profile.host_login}",
                "tracked_streams": row["tracked_streams"],
                "peak_viewers": row["peak_viewers"],
                "languages": sorted(lang.upper() for lang in row["languages"] if lang),
                "streams": streams_payload,
            })

        return search_results

    def _get_search_form(self):
        game_genres = GameGenre.objects.values_list("host_genre_id", "host_name")
        return {
            "title": "Search Streamers",
            "aria_label": "Demonstration search form",
            "filters": [
                self._get_search_form_field(
                    filter_type="dropdown",
                    filter_name="language",
                    filter_label="Language",
                    multi_values=[
                        {"value": "en", "l": "English"},
                        {"value": "fr", "l": "French"},
                        {"value": "de", "l": "German"}
                    ],
                    single_default="en",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="avg_viewers",
                    filter_label="Avg Viewers",
                    min_values=[{"v": "min", "l": "min"}] + self._get_quant_filter_values(),
                    min_default="min",
                    max_values=[{"v": "max", "l": "max"}] + self._get_quant_filter_values(),
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="max_viewers",
                    filter_label="Max Viewers",
                    min_values=[{"v": "min", "l": "min"}] + self._get_quant_filter_values(),
                    min_default="min",
                    max_values=[{"v": "max", "l": "max"}] + self._get_quant_filter_values(),
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="avg_duration",
                    filter_label="Avg Duration",
                    min_values=[{"v": "min", "l": "min"}] + self._get_time_filter_values(),
                    min_default="min",
                    max_values=[{"v": "max", "l": "max"}] + self._get_time_filter_values(),
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="max_duration",
                    filter_label="Max Duration",
                    min_values=[{"v": "min", "l": "min"}] + self._get_time_filter_values(),
                    min_default="min",
                    max_values=[{"v": "max", "l": "max"}] + self._get_time_filter_values(),
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="multiselect",
                    filter_name="genres",
                    filter_label="Game Genres",
                    multi_values=[{"v": str(one_value), "l": one_label} for one_value, one_label in game_genres],
                    multi_default=["4", "5", "12", "32", "24"],
                ),
                self._get_search_form_field(
                    filter_type="multiselect",
                    filter_name="week_days",
                    filter_label="Days of Week",
                    multi_values=[
                        {"v": "mon", "l": "Mon"},
                        {"v": "tue", "l": "Tue"},
                        {"v": "wed", "l": "Wed"},
                        {"v": "thu", "l": "Thu"},
                        {"v": "fri", "l": "Fri"},
                        {"v": "sat", "l": "Sat"},
                        {"v": "sun", "l": "Sun"},
                    ],
                    multi_default=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                ),
            ],
            "button_text": "Search",
            "demo_title": f"Note:",
            "demo_note": f"The search form is a demo example of the real search form which currently is under active development."
                f" The results below fit the the real search results for the search parameters prefilled in the form.",
        }

    def _update_home_page(self):
        total_streamers = StreamerProfile.objects.filter(streams__status=Stream.Status.APPROVED).distinct().count()
        total_streams = Stream.objects.filter(status=Stream.Status.APPROVED).count()

        content = {
            "title": f"IndieGameBridge",
            "description": f"Find Twitch streamers worth pitching your indie game to",
            "info": f"Currently tracking {total_streamers:,} streamers across {total_streams:,} observed streams",
            "project_goal": {
                "title": f"What is the project created for",
                "description": f"The project aims to help indie developers find and collaborate with streamers who regularly broadcast specific game genres to a relevant audience."
                    f" The platform accumulates only statistics data based on publicly available information provided by the Twitch streaming platform"
                    f" via the Helix API. We do not collect or share any private information. We only provide a link to the Twitch channel for the tracked streamers.",
            },
            "search_form": self._get_search_form(),
            "search_results": self._get_demo_search_results(),
            "roadmap": {
                "title": f"What's Coming",
                "description": f"The project is in an active development stage. The ranking table above is showing real data, which is updated hourly, but only for"
                    f" demonstration purposes. There are planned features which will include:",
                "features": [
                    f"Advanced search (available for registered users) - to find streamers by game genre, average and maximum viewers number, language, number of streams,"
                        f" duration of streams within a certain time frame or in total, and other useful search parameters.",
                    f"Export search results in preferred file format.",
                    f"Individual streamer page with detailed metrics for each stream.",
                    f"Other features under consideration.",
                    # Possible next features:
                    #   'Developer profile' with extra features:
                    #       - Create list of favorite streamers - select certain streamers from the search results and add them to the stored list (can be helpful to select
                    #           only certain streamers from the search results)
                    #       - Add notes for the streamers inside the favorite list - for example, notes whether and when the developer contacted the streamer and what the streamer
                    #           answered or ignored the message, etc - the communication is assumed outside the platform for now, but the notices can help to organize the search results
                    #       - Mark streamers inside the favorite list with different colors to visually distinguish them inside the list which may help to organize the list
                    #       - Sort streamers inside the favorite list - ability to change position of certain streamer in the list
                    #       - Common notes and custom names for each favorite list - this may help to organize different favorite lists for easier navigation between them
                    #       - Store up to N search results - this may help to return to the search results later and compare them with newest search results
                    #            (maybe + 'compare tool' to find intersection rows e.g. streamers who are present in 2 or more search results)
                    # MAYBE LATER:
                    #   'Streamer profile' - this may help streamers be found by developers who are interested in a collaboration where the
                    #       streamers can deliberately leave a message and contact information - probably, it will require manual moderation or via AI (or both)?
                    #   'Public developer profile' - if some developers want to use the platform as an additional advertisement channel for
                    #       their game(s) - probably, it will require manual moderation or via AI (or both)?
                ]
            },
            "methodology": {
                "title": f"Top Streamers",
                "description": f"We poll live streams every 20 minutes on the Twitch streaming platform via its Helix API."
                    f" Every snapshot contains game, number of viewers, date and time."
                    f" When a stream is off, we calculate the maximum number of viewers on the stream via snapshots history collected during the stream,"
                    f" and if the stream has at least 3 viewers in any of the snapshots, we add the stream to the streamer's statistics.",
            },
            "cta": {
                "title": f"Get notified when advanced search goes live",
                "input_placeholder": "your@email.com",
                "btn_text": "Notify Me",
            },
            "data_source": f"Data sourced from public Twitch streams. Streamers can opt out at any time.",
        }

        CachedPage.objects.update_or_create(
            key="home",
            defaults={"content": content},
        )

        logger.info(
            "Home page cache updated:%s total streamers, %s total streams",
            total_streamers, total_streams,
        )
