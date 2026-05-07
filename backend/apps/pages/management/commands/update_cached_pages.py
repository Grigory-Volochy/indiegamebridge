import logging

from django.contrib.postgres.aggregates import ArrayAgg
from django.core.management.base import BaseCommand
from django.db.models import Count, Max

from apps.pages.models import CachedPage
from apps.streams.models import Stream, StreamerProfile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Recomputes pre-rendered page payloads stored in the CachedPage table."

    # Cap on rows in the home page leaderboard.
    home_top_n = 100

    def handle(self, *args, **kwargs):
        logger.info("Updating cached pages...")
        self._update_home_page()
        logger.info("Cached pages update finished.")

    def _update_home_page(self):
        # Aggregate per streamer over their finalized (offline) streams only.
        # Live streams have max_viewers=0 until finalize_offline_streams runs,
        # so including them would skew the leaderboard.
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

        table_rows = []
        for row in top_aggregates:
            profile = profiles_by_id.get(row["streamer_profile_id"])
            if profile is None:
                continue
            table_rows.append({
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
            "title": "IndieGameBridge",
            "description": "Find Twitch streamers worth pitching your indie game to",
            "info": f"Currently tracking {total_streamers} streamers across {total_streams} observed streams",
            "table_rows": table_rows,
        }

        CachedPage.objects.update_or_create(
            key="home",
            defaults={"content": content},
        )

        logger.info(
            "Home page cache updated: %s rows, %s total streamers, %s total streams",
            len(table_rows), total_streamers, total_streams,
        )
