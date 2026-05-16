from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import User, TwitchExclusion


admin.site.register(User, UserAdmin)


@admin.register(TwitchExclusion)
class TwitchExclusionAdmin(admin.ModelAdmin):
    list_display = ("twitch_id", "optout_at")
    search_fields = ("twitch_id",)
    ordering = ("-optout_at",)
    readonly_fields = ("optout_at",)
