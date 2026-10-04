from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Bill
from inventory.models import InventoryItem, InventoryTransaction
from orders.models import Order, OrderItem
from restaurants.models import Restaurant
from restaurants.permissions import MANAGER_ROLES, has_restaurant_access, restaurant_scope


CENT = Decimal("0.01")
INVENTORY_DECIMALS = Decimal("0.000000")


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def quantize_quantity(value):
    return Decimal(value).quantize(INVENTORY_DECIMALS, rounding=ROUND_HALF_UP)


class AnalyticsAccessPermission(BasePermission):
	def has_permission(self, request, view):
		user = request.user
		if not user or not user.is_authenticated:
			return False
		return bool(
			user.is_superuser
			or Restaurant.objects.filter(owner=user).exists()
			or user.restaurant_memberships.filter(
				role__in=MANAGER_ROLES,
				is_active=True,
			).exists()
		)


def _date_from_query(value, field_name):
	try:
		return date.fromisoformat(value)
	except (TypeError, ValueError):
		raise ValidationError({field_name: "Use an ISO date in YYYY-MM-DD format."})


def _period_dates(request):
	period = request.query_params.get("period", "today")
	today = timezone.localdate()

	if period == "today":
		start_date = end_date = today
	elif period == "yesterday":
		start_date = end_date = today - timedelta(days=1)
	elif period == "7d":
		start_date, end_date = today - timedelta(days=6), today
	elif period == "30d":
		start_date, end_date = today - timedelta(days=29), today
	elif period == "custom":
		start_date = _date_from_query(request.query_params.get("start"), "start")
		end_date = _date_from_query(request.query_params.get("end"), "end")
		if start_date > end_date:
			raise ValidationError({"end": "End date must be on or after start date."})
		if (end_date - start_date).days > 365:
			raise ValidationError({"end": "Custom ranges cannot exceed 366 calendar days."})
	else:
		raise ValidationError({"period": "Choose today, yesterday, 7d, 30d, or custom."})

	current_timezone = timezone.get_current_timezone()
	start_at = timezone.make_aware(datetime.combine(start_date, time.min), current_timezone)
	end_at = timezone.make_aware(
		datetime.combine(end_date + timedelta(days=1), time.min),
		current_timezone,
	)
	return period, start_date, end_date, start_at, end_at, current_timezone


class DashboardAnalyticsView(APIView):
	permission_classes = [AnalyticsAccessPermission]

	def get(self, request):
		user = request.user
		accessible_restaurants = Restaurant.objects.filter(restaurant_scope(user)).distinct()
		if user.is_superuser:
			accessible_restaurants = Restaurant.objects.all()

		restaurant_id = request.query_params.get("restaurant")
		if restaurant_id:
			if not restaurant_id.isdecimal():
				raise ValidationError({"restaurant": "Restaurant must be a numeric ID."})
			restaurant = accessible_restaurants.filter(id=int(restaurant_id)).first()
			if restaurant is None:
				raise NotFound("Restaurant analytics are not available to this account.")
		else:
			restaurant = accessible_restaurants.order_by("id").first()
			if restaurant is None:
				raise NotFound("No restaurant is available for analytics.")

		period, start_date, end_date, start_at, end_at, current_timezone = _period_dates(request)
		orders = Order.objects.filter(
			restaurant=restaurant,
			created_at__gte=start_at,
			created_at__lt=end_at,
		)
		paid_bills = Bill.objects.filter(
			restaurant=restaurant,
			payment_status=Order.PaymentStatus.PAID,
			paid_at__gte=start_at,
			paid_at__lt=end_at,
			order__status__in=[status for status, _label in Order.Status.choices if status != Order.Status.CANCELLED],
		)
		unpaid_bills = Bill.objects.filter(
			restaurant=restaurant,
			payment_status=Order.PaymentStatus.UNPAID,
			issued_at__gte=start_at,
			issued_at__lt=end_at,
			order__status__in=[status for status, _label in Order.Status.choices if status != Order.Status.CANCELLED],
		)

		paid_totals = paid_bills.aggregate(
			revenue=Sum("total_amount"),
			count=Count("id"),
		)
		unpaid_totals = unpaid_bills.aggregate(
			amount=Sum("total_amount"),
			count=Count("id"),
		)
		collected_revenue = paid_totals["revenue"] or Decimal("0.00")
		paid_bill_count = paid_totals["count"] or 0

		status_counts = {
			row["status"]: row["count"]
			for row in orders.values("status").annotate(count=Count("id"))
		}
		status_distribution = [
			{"status": order_status, "count": status_counts.get(order_status, 0)}
			for order_status, _label in Order.Status.choices
		]

		revenue_rows = (
			paid_bills.annotate(day=TruncDate("paid_at", tzinfo=current_timezone))
			.values("day")
			.annotate(revenue=Sum("total_amount"))
			.order_by("day")
		)
		revenue_by_day = {row["day"]: row["revenue"] for row in revenue_rows}
		revenue_trend = [
			{
				"date": (start_date + timedelta(days=offset)).isoformat(),
				"revenue": str(money(revenue_by_day.get(start_date + timedelta(days=offset)) or Decimal("0.00"))),
			}
			for offset in range((end_date - start_date).days + 1)
		]

		popular_items = (
			OrderItem.objects.filter(
				order__restaurant=restaurant,
				order__created_at__gte=start_at,
				order__created_at__lt=end_at,
			)
			.exclude(order__status=Order.Status.CANCELLED)
			.values("menu_item_id", "menu_item__name")
			.annotate(quantity_sold=Sum("quantity"), item_revenue=Sum("subtotal"))
			.order_by("-quantity_sold", "-item_revenue", "menu_item__name")[:10]
		)

		payment_methods = [
			{
				"method": row["payment_method"] or "OTHER",
				"amount": str(money(row["amount"] or Decimal("0.00"))),
				"count": row["count"],
			}
			for row in paid_bills.values("payment_method").annotate(
				amount=Sum("total_amount"),
				count=Count("id"),
			).order_by("payment_method")
		]

		inventory_item_count = InventoryItem.objects.filter(
			restaurant=restaurant,
			is_active=True,
		).count()
		stock_rows = (
			InventoryTransaction.objects.filter(
				inventory_item__restaurant=restaurant,
				source=InventoryTransaction.Source.ORDER,
				created_at__gte=start_at,
				created_at__lt=end_at,
			)
			.values("inventory_item_id", "inventory_item__name", "inventory_item__unit")
			.annotate(
				order_out=Sum("quantity", filter=Q(transaction_type=InventoryTransaction.Type.OUT)),
				reversal=Sum("quantity", filter=Q(transaction_type=InventoryTransaction.Type.REVERSAL)),
			)
			.order_by("inventory_item__name")
		)
		order_stock_usage = []
		for row in stock_rows:
			quantity_used = (row["order_out"] or Decimal("0")) - (row["reversal"] or Decimal("0"))
			if quantity_used > 0:
				order_stock_usage.append({
					"inventory_item_id": row["inventory_item_id"],
					"name": row["inventory_item__name"],
					"unit": row["inventory_item__unit"],
					"quantity_used": str(quantize_quantity(quantity_used)),
				})

		order_count = orders.count()
		return Response({
			"restaurant": {"id": restaurant.id, "name": restaurant.name},
			"period": {
				"key": period,
				"start": start_date.isoformat(),
				"end": end_date.isoformat(),
				"timezone": settings.TIME_ZONE,
			},
			"currency": "USD",
			"metrics": {
				"collected_revenue": str(money(collected_revenue)),
				"total_orders": order_count,
				"paid_orders": orders.filter(payment_status=Order.PaymentStatus.PAID).count(),
				"unpaid_orders": orders.filter(payment_status=Order.PaymentStatus.UNPAID).count(),
				"completed_orders": status_counts.get(Order.Status.COMPLETED, 0),
				"cancelled_orders": status_counts.get(Order.Status.CANCELLED, 0),
				"average_paid_bill_value": str(
					money(collected_revenue / paid_bill_count if paid_bill_count else Decimal("0.00"))
				),
				"paid_bill_count": paid_bill_count,
				"unpaid_bill_count": unpaid_totals["count"] or 0,
				"unpaid_bill_amount": str(money(unpaid_totals["amount"] or Decimal("0.00"))),
				"active_inventory_item_count": inventory_item_count,
			},
			"revenue_trend": revenue_trend,
			"order_status_distribution": status_distribution,
			"popular_items": [
				{
					"menu_item_id": row["menu_item_id"],
					"name": row["menu_item__name"],
					"quantity_sold": row["quantity_sold"] or 0,
					"item_revenue": str(money(row["item_revenue"] or Decimal("0.00"))),
				}
				for row in popular_items
			],
			"payment_methods": payment_methods,
			"inventory": {
				"active_item_count": inventory_item_count,
			},
			"inventory_order_usage": order_stock_usage,
		})
