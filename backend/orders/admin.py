from django.contrib import admin

# Register your models here.

from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "restaurant",
        "table",
        "customer_name",
        "status",
        "payment_status",
        "total_amount",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_status",
        "restaurant",
    )

    search_fields = (
        "customer_name",
        "customer_phone",
    )

    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "menu_item",
        "quantity",
        "unit_price",
        "subtotal",
    )

    search_fields = (
        "menu_item__name",
    )