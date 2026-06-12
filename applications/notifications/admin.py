from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):

    list_display = (
        "titre",
        "utilisateur",
        "type",
        "lu",
        "date_creation",
    )

    list_filter = (
        "type",
        "lu",
        "date_creation",
    )

    search_fields = (
        "titre",
        "message",
        "utilisateur__username",
        "utilisateur__first_name",
        "utilisateur__last_name",
    )

    ordering = (
        "-date_creation",
    )

    readonly_fields = (
        "date_creation",
        "date_lecture",
    )