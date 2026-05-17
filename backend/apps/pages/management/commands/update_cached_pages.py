import logging
from datetime import timedelta

from django.contrib.postgres.aggregates import JSONBAgg
from django.core.management.base import BaseCommand
from django.db.models import Max, Avg, Min, F
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
        self._update_opt_out_page()
        self._update_contact_page()
        self._update_login_page()
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
        return f"{hours} h " + f"{minutes} min"

    def _get_demo_search_results(self) -> tuple[list[dict]]:
        # Hardcoded filter values for the demo. The real search will expose these via the form.
        demo_language = "en"
        demo_window_start = timezone.now() - timedelta(days=14)
        demo_weekdays = [1, 2, 3, 4, 5, 6, 7]
        demo_min_duration = 1800
        demo_max_duration = 36000
        demo_min_viewers = 100
        demo_max_viewers = 100000
        demo_genre_ids = [5]  # GameGenre.host_genre_id values

        # Aggregate top streamers from the filtered stream set.
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
                login=F("host_login"),
                display_name=F("host_display_name"),
                profile_id=F("streamer_profile_id")
            )
            .annotate(
                peak_viewers=Max("max_viewers"),
                max_duration=Max("duration"),
                avg_duration=Avg("duration"),
                min_duration=Min("duration"),
                streams=JSONBAgg(
                    JSONObject(
                        id="id",
                        duration="duration",
                        max_viewers="max_viewers",
                        language="language",
                        game_ids="host_game_ids",
                        started_at="started_at",
                        finished_at="finished_at"
                    )
                )
            )
            .order_by("-peak_viewers")[: self.home_top_n]
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

        # Replace game_ids with human-readable game names and format the duration.
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
                    filter_label="Time Window *",
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
                    filter_label="Days of Week *",
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
            "button_text": "Apply Filters",
            "demo_title": f"Note:",
            "search_notes": [
                "Times are in UTC. Days of week and the time window are both based on when each stream went offline. A UTC day can straddle two local days in non-UTC zones."
            ],
            "demo_note": f"The search form is a demo of the real search form, which is available for logged in users."
                f" The results below are real, matching the search parameters prefilled in the form and updating hourly.",
            "cta_link_text": f"Log in to use the search"
        }

    def _update_home_page(self):
        total_streamers = StreamerProfile.objects.filter(streams__status=Stream.Status.APPROVED).distinct().count()
        total_streams = Stream.objects.filter(status=Stream.Status.APPROVED).count()

        content = {
            "title": f"IndieGameBridge",
            "description": f"Find Twitch streamers worth pitching your indie game to",
            "info": f"Currently tracking {total_streamers:,} streamers across {total_streams:,} observed streams",
            "project_goal": {
                "title": f"What this project is for",
                "description": f"The project aims to help indie developers find and collaborate with streamers who regularly broadcast specific game genres to a relevant audience."
                    f" The platform only aggregates statistics from publicly available information provided by Twitch via the Helix API."
                    f" We do not collect or share any private information.",
            },
            "search_form": self._get_search_form(),
            "search_results_title": "Search Results",
            "search_results": self._get_demo_search_results(),
            "roadmap": {
                "title": f"What's Coming",
                "description": f"The project is in active development."
                    f" Planned features include:",
                "features": [
                    f"Export search results in your preferred file format.",
                    f"Developer profile with extra features.",
                    f"Streamer profile with extra features.",
                    # Possible next features:
                    #   'Developer profile' with extra features:
                    #       - Create a favorites list of streamers - pick selected streamers from the search results and save them to a stored list
                    #           (useful for narrowing a larger result set down to the ones worth following up on).
                    #       - Add notes to streamers in the favorites list - e.g. whether and when the developer contacted the streamer, and what the streamer
                    #           replied or whether they ignored the message. Communication itself is assumed to happen outside the platform for now, but these notes
                    #           help organize the search results.
                    #       - Mark streamers in the favorites list with different colors to visually distinguish them - helps with organization.
                    #       - Sort streamers in the favorites list - reorder entries manually.
                    #       - Per-list notes and custom names for each favorites list - makes it easier to navigate between multiple lists.
                    #       - Store up to N past search results - lets the user revisit previous searches and compare them with newer ones
                    #           (maybe also a 'compare tool' to find streamers appearing in two or more search results).
                    # MAYBE LATER:
                    #   'Streamer profile' - lets streamers be discovered by developers interested in collaboration; streamers can voluntarily
                    #       leave a message and contact info. Likely needs manual moderation, AI moderation, or both.
                    #   'Public developer profile' - for developers who want to use the platform as an additional promotion channel
                    #       for their game(s). Likely needs manual moderation, AI moderation, or both.
                    #   Features to make communication easier on both sides (the idea is to offer a dedicated place for communication without forcing anyone
                    #   to use the platform if they prefer other channels):
                    #       - direct messages
                    #       - built-in Zoom-style calls and meetings
                    #       - ratings and statistics
                    #       - integrated promo codes (to make collaboration more automated and reduce overhead for both sides)
                    #       - AI best-match search (a quick-start option for users who don't want to spend time on a thorough search or want to reduce overhead)
                ]
            },
            "methodology": {
                "title": f"Methodology",
                "description": f"We poll live Twitch streams every 20 minutes via the Helix API."
                    f" Each snapshot records the game, viewer count, date, and time."
                    f" Once a stream ends, we compute its peak viewer count from the snapshots collected while it was live,"
                    f" and if any snapshot recorded at least 3 viewers, we add the stream to the streamer's statistics.",
            },
            "cta": {
                "title": f"Get notified when advanced search goes live",
                "input_placeholder": "your@email.com",
                "btn_text": "Notify Me",
            },
            "data_source": f"Data sourced from public Twitch streams. Streamers can %opt_out_link% at any time.",
            "opt_out_text": "opt out",
            "footer_links": [
                {
                    "text": "Request removal",
                    "url": "/optout",
                    "nofollow": 1,
                },
                {
                    "text": "GitHub",
                    "url": "/https://github.com/IndieGameBridge/indiegamebridge",
                    "nofollow": 1,
                },
                {
                    "text": "Contact",
                    "url": "/contact",
                    "nofollow": 1,
                }
            ],
        }

        CachedPage.objects.update_or_create(
            key="home",
            defaults={"content": content},
        )

        logger.info(
            "Home page cache updated:%s total streamers, %s total streams",
            total_streamers, total_streams,
        )

    def _update_opt_out_page(self):
        content = {
            "title": f"Opt Out",
            "return_home": f"Return to Home Page",
            "not_logged_in": {
                "prompt": f"Want to opt out? Click below to log in with your Twitch account so we can verify your Twitch ID. We will then remove all data tied to it and exclude it from future collection.",
                "login_btn": f"Log in with Twitch to verify your Twitch ID",
            },
            "logged_in": {
                "prompt": f"Want to opt out? Click below to confirm. We will remove all data tied to your Twitch ID and exclude it from future collection.",
                "optout_btn": f"Opt Out",
            },
            "already_optout": f"You have already opted out, and we have handled it. No action required - we no longer collect or store any data about your streams.",
            "success_optout": f"We have verified your Twitch ID and removed all data tied to it. Going forward, we will exclude it from future collection. The public page may still show your data for up to an hour while caches refresh.",
        }

        CachedPage.objects.update_or_create(
            key="optout",
            defaults={"content": content},
        )

        logger.info("Opt-out page cache updated.")

    def _update_contact_page(self):
        content = {
            "title": f"Contact",
            "return_home": f"Return to Home Page",
            "body": f"Contact details are coming soon. In the meantime, please reach out via the project's GitHub repository.",
        }

        CachedPage.objects.update_or_create(
            key="contact",
            defaults={"content": content},
        )

        logger.info("Contact page cache updated.")

    def _update_login_page(self):
        content = {
            "title": f"Log in",
            "prompt": f"IndieGameBridge uses your Twitch account to verify you. We never see your password.",
            "twitch_login_btn": f"Log in with Twitch",
            "more_options_note": f"More login options coming later.",
        }

        CachedPage.objects.update_or_create(
            key="login",
            defaults={"content": content},
        )

        logger.info("Login page cache updated.")
