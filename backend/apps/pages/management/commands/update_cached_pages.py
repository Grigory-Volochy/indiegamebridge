import logging
from datetime import timedelta
import json

from django.contrib.postgres.aggregates import ArrayAgg, JSONBAgg
from django.core.management.base import BaseCommand
from django.db.models import Count, Max, Avg, Min, F
from django.db.models.functions import ExtractIsoWeekDay, JSONObject
from django.utils import timezone

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
            {"v": "20m", "l": "20 min"},
            {"v": "1h", "l": "1 h"},
            {"v": "2h", "l": "2 h"},
            {"v": "3h", "l": "3 h"},
            {"v": "6h", "l": "6 h"},
            {"v": "9h", "l": "9 h"},
            {"v": "12h", "l": "12 h"},
            {"v": "24h", "l": "24 h"}
        ]
    
    def _format_duration(self, duration=0):
        hours, r = divmod(duration, 3600)
        minutes, r = divmod(r, 60)
        return f"{hours} h | " + f"{minutes} min"

    def _get_demo_search_results(self) -> tuple[list[dict]]:
        # Hardcoded search filter values for demo purpose - will be exposed via the search form in the real search.
        demo_language = "en"
        demo_window_start = timezone.now() - timedelta(days=7)
        demo_weekdays = [1, 2, 3, 4, 5, 6, 7]
        demo_min_duration = 1800
        demo_max_duration = 36000
        demo_min_viewers = 100
        demo_max_viewers = 100000
        demo_genre_ids = [5]  # GameGenre.host_genre_id values

        # Select top streamers with streams depending on the filtered streams list.
        top_streamer_aggregates = list(
            Stream.objects.filter(
                status=Stream.Status.APPROVED,
                finished_at__gte=demo_window_start,
                language=demo_language,
                duration__gte=demo_min_duration,
                duration__lte=demo_max_duration,
                max_viewers__gte=demo_min_viewers,
                max_viewers__lte=demo_max_viewers,
                genre_ids__overlap=demo_genre_ids
            )
            .annotate(
                finished_dow=ExtractIsoWeekDay("finished_at")
            )
            .filter(
                finished_dow__in=demo_weekdays
            )
            .annotate(
                host_login=F("streamer_profile__host_login"),
                host_display_name=F("streamer_profile__host_display_name")
            )
            .values(
                loging=F("host_login"),
                display_name=F("host_display_name"),
                profile_id=F("streamer_profile_id")
            )
            .annotate(
                tracked_streams=Count("id"),
                peak_viewers=Max("max_viewers"),
                max_duration=Max("duration"),
                avg_duration=Avg("duration"),
                min_duration=Min("duration"),
                languages=ArrayAgg("language", distinct=True),
                streams=JSONBAgg(
                    JSONObject(
                        id="id",
                        duration="duration",
                        max_viewers="max_viewers",
                        language="language",
                        game_ids="host_game_ids"
                    )
                )
            )
            .order_by("-peak_viewers", "-tracked_streams")[: self.home_top_n]
        )

        # Resolve every referenced game in a single query.
        all_game_ids = {
            one_game_id
            for one_streamer in top_streamer_aggregates
            for one_stream in one_streamer.get("streams", [])
            for one_game_id in one_stream.get("game_ids", [])
        }

        game_names_map = dict(
            Game.objects.filter(host_game_id__in=all_game_ids)
            .values_list("host_game_id", "host_name")
        )

        # replace
        for one_streamer in top_streamer_aggregates:
            for stream in one_streamer.get("streams", []):
                stream["games"] = [
                    game_names_map.get(game_id, "N/A")
                    for game_id in (stream.get("game_ids") or [])
                ]
                stream["duration"] = self._format_duration(duration=stream["duration"])
                stream.pop("game_ids", None)

        return top_streamer_aggregates 

    def _get_search_form(self):
        game_genres = [("any", "Any genre")] + list(GameGenre.objects.values_list("host_genre_id", "host_name"))
        return {
            "title": "Search Streamers",
            "aria_label": "Demonstration search form",
            "filters": [
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
                    filter_name="avg_viewers",
                    filter_label="Avg Viewers",
                    min_values=[{"v": "min", "l": "min"}] + self._get_quant_filter_values(),
                    min_default="min",
                    max_values=[{"v": "max", "l": "max"}] + self._get_quant_filter_values(),
                    max_default="max",
                ),
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
                    filter_name="duration",
                    filter_label="Duration",
                    min_values=[{"v": "min", "l": "min"}] + self._get_time_filter_values(),
                    min_default="min",
                    max_values=[{"v": "max", "l": "max"}] + self._get_time_filter_values(),
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="dropdown",
                    filter_name="time_window",
                    filter_label="Time Window",
                    multi_values=[
                        {"v": "7", "l": "1 Week"},
                        {"v": "14", "l": "2 Weeks"},
                        {"v": "21", "l": "3 Weeks"},
                        {"v": "28", "l": "4 Weeks"},
                    ],
                    multi_default=["7"],
                ),
                self._get_search_form_field(
                    filter_type="dropdown",
                    filter_name="genre",
                    filter_label="Game Genre",
                    multi_values=[{"v": str(one_value), "l": one_label} for one_value, one_label in game_genres],
                    multi_default=["any"],
                ),
                self._get_search_form_field(
                    filter_type="multiselect",
                    filter_name="week_days",
                    filter_label="Days of Week",
                    multi_values=[
                        {"v": "1", "l": "Mon"},
                        {"v": "2", "l": "Tue"},
                        {"v": "3", "l": "Wed"},
                        {"v": "4", "l": "Thu"},
                        {"v": "5", "l": "Fri"},
                        {"v": "6", "l": "Sat"},
                        {"v": "7", "l": "Sun"},
                    ],
                    multi_default=["1", "5", "6", "7"],
                ),
            ],
            "button_text": "Search",
            "demo_title": f"Note:",
            "search_notes": [
                "* Times are UTC. Day-of-week and the days window both key off when each stream went offline; UTC days can straddle two local days in non-UTC zones."
            ],
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
                    #   Features for make the communication easier for both sides (the idea is to provide dedicated place for communication and not to force anyone to use the platform for this if they prefer another communication channels):
                    #       - direct messages
                    #       - built-in Zoom calls and meetings or similar
                    #       - ratings and statistics
                    #       - integrated promocodes (to make collaboration more automated and reduce overhead costs for both sides)
                    #       - AI best matching search (as a quick start option for those, who don't like spend time for thorough search pr want to reduce overhead costs)
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
