from django.contrib import admin

from .models import Bill, BillLine


class BillLineInline(admin.TabularInline):
    model = BillLine
    extra = 0
    can_delete = False
    readonly_fields = tuple(field.name for field in BillLine._meta.fields)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "restaurant",
        "total_amount",
        "payment_status",
        "payment_method",
        "issued_at",
        "paid_at",
    )
    list_filter = ("payment_status", "payment_method", "restaurant")
    search_fields = ("order__id", "restaurant__name")
    readonly_fields = tuple(field.name for field in Bill._meta.fields)
    inlines = [BillLineInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False
