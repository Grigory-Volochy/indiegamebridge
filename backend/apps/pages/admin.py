from django.contrib import admin

from apps.pages.models import CachedPage


@admin.register(CachedPage)
class CachedPageAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")
    readonly_fields = ("updated_at",)
    search_fields = ("key",)
