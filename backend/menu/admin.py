from django.contrib import admin
from .models import Category, MenuItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "is_active", "created_at")
    search_fields = ("name", "restaurant__name")
    list_filter = ("is_active",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "restaurant",
        "category",
        "price",
        "is_available",
        "is_featured",
    )

    search_fields = ("name", "restaurant__name")
    list_filter = ("is_available", "is_featured", "category")