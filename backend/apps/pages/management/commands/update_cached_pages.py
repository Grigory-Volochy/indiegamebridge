import logging

from django.contrib.postgres.aggregates import ArrayAgg
from django.core.management.base import BaseCommand
from django.db.models import Count, Max

from apps.streams.models import Stream, StreamerProfile
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
            "multi_labels": [],
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

    def _update_home_page(self):
        # Aggregate per streamer over their finalized (offline) streams only.
        # Live streams have max_viewers=0 until finalize_offline_streams runs,
        # so including them would skew the search results.
        # Future ExcludedStreamers integration: add `.exclude(streamer_profile_id__in=excluded_ids)`
        # to this queryset before the slice.
        top_aggregates = list(
            Stream.objects.filter(status=Stream.Status.OFFLINE)
            .values("streamer_profile_id")
            .annotate(
                tracked_streams=Count("id"),
                peak_viewers=Max("max_viewers"),
                languages=ArrayAgg("language", distinct=True),
            )
            .order_by("-peak_viewers")[: self.home_top_n]
        )

        profile_ids = [row["streamer_profile_id"] for row in top_aggregates]
        profiles_by_id = {
            profile.id: profile
            for profile in StreamerProfile.objects.filter(id__in=profile_ids).only(
                "id", "host_login", "host_display_name"
            )
        }

        search_form = {
            "title": "Filter Streamers",
            "aria_label": "Demonstration search form",
            "filters": [
                self._get_search_form_field(
                    filter_type="dropdown",
                    filter_name="language",
                    filter_label="Language",
                    multi_values=["en", "fr", "de"],
                    multi_labels=["English", "French", "German"],
                    single_default="en",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="avg_viewers",
                    filter_label="Avg Viewers",
                    min_values=["min", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    min_labels=["min", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    min_default="min",
                    max_values=["max", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    max_labels=["max", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="max_viewers",
                    filter_label="Max Viewers",
                    min_values=["min", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    min_labels=["min", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    min_default="min",
                    max_values=["max", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    max_labels=["max", "3", "10", "50", "100", "500", "1000", "5000", "10000", "50000", "100000"],
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="avg_duration",
                    filter_label="Avg Duration",
                    min_values=["min", "20m", "1h", "2h", "3h", "6h", "9h", "12h", "24h"],
                    min_labels=["min", "20 minutes", "1 Hour", "2 Hours", "3 Hours", "6 Hours", "9 Hours", "12 Hours", "24 Hours"],
                    min_default="min",
                    max_values=["max", "20m", "1h", "2h", "3h", "6h", "9h", "12h", "24h"],
                    max_labels=["max", "20 minutes", "1 Hour", "2 Hours", "3 Hours", "6 Hours", "9 Hours", "12 Hours", "24 Hours"],
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="range",
                    filter_name="max_duration",
                    filter_label="Max Duration",
                    min_values=["min", "20m", "1h", "2h", "3h", "6h", "9h", "12h", "24h"],
                    min_labels=["min", "20 minutes", "1 Hour", "2 Hours", "3 Hours", "6 Hours", "9 Hours", "12 Hours", "24 Hours"],
                    min_default="min",
                    max_values=["max", "20m", "1h", "2h", "3h", "6h", "9h", "12h", "24h"],
                    max_labels=["max", "20 minutes", "1 Hour", "2 Hours", "3 Hours", "6 Hours", "9 Hours", "12 Hours", "24 Hours"],
                    max_default="max",
                ),
                self._get_search_form_field(
                    filter_type="multiselect",
                    filter_name="week_days",
                    filter_label="Days of Week",
                    multi_values=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                    multi_labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    multi_default=["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                ),
            ]
        }

        search_results = []
        for row in top_aggregates:
            profile = profiles_by_id.get(row["streamer_profile_id"])
            if profile is None:
                continue
            search_results.append({
                "display_name": profile.host_display_name,
                "login": profile.host_login,
                "twitch_url": f"https://twitch.tv/{profile.host_login}",
                "tracked_streams": row["tracked_streams"],
                "peak_viewers": row["peak_viewers"],
                "languages": sorted(lang.upper() for lang in row["languages"] if lang),
            })

        total_streamers = StreamerProfile.objects.count()
        total_streams = Stream.objects.count()

        content = {
            "title": f"IndieGameBridge",
            "description": f"Find Twitch streamers worth pitching your indie game to",
            "info": f"Currently tracking {total_streamers} streamers across {total_streams} observed streams",
            "project_goal": {
                "title": f"What is the project created for",
                "description": f"The project aims to help indie developers find and collaborate with streamers who regularly broadcast specific game genres to a relevant audience."
                    f" The platform accumulates only statistics data based on publicly available information provided by the Twitch streaming platform"
                    f" via the Helix API. We do not collect or share any private information. We only provide a link to the Twitch channel for the tracked streamers.",
            },
            "search_form": search_form,
            "search_results": search_results,
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
            "Home page cache updated: %s rows, %s total streamers, %s total streams",
            len(search_results), total_streamers, total_streams,
        )
