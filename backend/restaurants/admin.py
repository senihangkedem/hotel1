from django.contrib import admin
from .models import Restaurant, RestaurantStaff, RestaurantTable


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "phone", "is_active", "created_at")
    search_fields = ("name", "owner__username")
    list_filter = ("is_active",)


@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "table_number", "capacity", "is_active")
    search_fields = ("restaurant__name",)
    list_filter = ("is_active",)


@admin.register(RestaurantStaff)
class RestaurantStaffAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurant", "role", "is_active", "created_at")
    search_fields = ("user__username", "restaurant__name")
    list_filter = ("role", "is_active")