from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from billing.models import Bill
from inventory.models import InventoryItem, InventoryTransaction
from menu.models import MenuItem
from orders.models import Order, OrderItem
from restaurants.models import Restaurant, RestaurantStaff


User = get_user_model()


class AnalyticsDashboardTests(APITestCase):
	def setUp(self):
		self.owner_a = User.objects.create_user("analytics-owner-a", password="test-password", role="OWNER")
		self.owner_b = User.objects.create_user("analytics-owner-b", password="test-password", role="OWNER")
		self.manager_a = User.objects.create_user("analytics-manager-a", password="test-password", role="MANAGER")
		self.waiter_a = User.objects.create_user("analytics-waiter-a", password="test-password", role="WAITER")
		self.customer_a = User.objects.create_user("analytics-customer-a", password="test-password", role="CUSTOMER")
		self.customer_b = User.objects.create_user("analytics-customer-b", password="test-password", role="CUSTOMER")
		self.restaurant_a = Restaurant.objects.create(
			owner=self.owner_a,
			name="Analytics A",
			address="1 Data Way",
		)
		self.restaurant_b = Restaurant.objects.create(
			owner=self.owner_b,
			name="Analytics B",
			address="2 Data Way",
		)
		RestaurantStaff.objects.create(user=self.manager_a, restaurant=self.restaurant_a, role=User.Role.MANAGER)
		RestaurantStaff.objects.create(user=self.waiter_a, restaurant=self.restaurant_a, role=User.Role.WAITER)
		self.today = timezone.localdate()
		self.start = timezone.make_aware(
			datetime.combine(self.today, time.min),
			timezone.get_current_timezone(),
		)
		self.momo = MenuItem.objects.create(
			restaurant=self.restaurant_a,
			name="Chicken Momo",
			price="50.00",
		)
		self.other_item = MenuItem.objects.create(
			restaurant=self.restaurant_b,
			name="Other Dish",
			price="999.00",
		)
		self.paid_order = Order.objects.create(
			restaurant=self.restaurant_a,
			customer=self.customer_a,
			status=Order.Status.COMPLETED,
			payment_status=Order.PaymentStatus.PAID,
			total_amount="100.00",
			customer_phone="555-private",
		)
		self.unpaid_order = Order.objects.create(
			restaurant=self.restaurant_a,
			customer=self.customer_a,
			status=Order.Status.PREPARING,
			payment_status=Order.PaymentStatus.UNPAID,
			total_amount="80.00",
		)
		self.cancelled_order = Order.objects.create(
			restaurant=self.restaurant_a,
			customer=self.customer_a,
			status=Order.Status.CANCELLED,
			payment_status=Order.PaymentStatus.UNPAID,
			total_amount="300.00",
		)
		self.other_order = Order.objects.create(
			restaurant=self.restaurant_b,
			customer=self.customer_b,
			status=Order.Status.COMPLETED,
			payment_status=Order.PaymentStatus.PAID,
			total_amount="999.00",
		)
		self.paid_bill = Bill.objects.create(
			order=self.paid_order,
			restaurant=self.restaurant_a,
			subtotal="100.00",
			tax_rate="10.00",
			tax_amount="10.00",
			service_charge_rate="5.00",
			service_charge_amount="5.00",
			total_amount="115.00",
			payment_status=Order.PaymentStatus.PAID,
			payment_method=Bill.PaymentMethod.CASH,
		)
		self.unpaid_bill = Bill.objects.create(
			order=self.unpaid_order,
			restaurant=self.restaurant_a,
			subtotal="80.00",
			total_amount="88.00",
			payment_status=Order.PaymentStatus.UNPAID,
		)
		self.cancelled_paid_bill = Bill.objects.create(
			order=self.cancelled_order,
			restaurant=self.restaurant_a,
			subtotal="300.00",
			total_amount="300.00",
			payment_status=Order.PaymentStatus.PAID,
			payment_method=Bill.PaymentMethod.QR,
		)
		self.other_bill = Bill.objects.create(
			order=self.other_order,
			restaurant=self.restaurant_b,
			subtotal="999.00",
			total_amount="999.00",
			payment_status=Order.PaymentStatus.PAID,
			payment_method=Bill.PaymentMethod.CARD,
		)
		# Keep paid_at deterministic and make the cancelled payment an explicit exclusion case.
		Bill.objects.filter(id__in=[self.paid_bill.id, self.cancelled_paid_bill.id, self.other_bill.id]).update(paid_at=timezone.now())
		Bill.objects.filter(id=self.unpaid_bill.id).update(issued_at=timezone.now())
		OrderItem.objects.create(
			order=self.paid_order,
			menu_item=self.momo,
			quantity=2,
			unit_price="50.00",
			subtotal="100.00",
		)
		OrderItem.objects.create(
			order=self.unpaid_order,
			menu_item=self.momo,
			quantity=4,
			unit_price="20.00",
			subtotal="80.00",
		)
		OrderItem.objects.create(
			order=self.cancelled_order,
			menu_item=self.momo,
			quantity=10,
			unit_price="30.00",
			subtotal="300.00",
		)
		OrderItem.objects.create(
			order=self.other_order,
			menu_item=self.other_item,
			quantity=1,
			unit_price="999.00",
			subtotal="999.00",
		)
		self.stock = InventoryItem.objects.create(
			restaurant=self.restaurant_a,
			name="Chicken",
			unit=InventoryItem.Unit.KILOGRAM,
			quantity_on_hand="4.500000",
		)
		InventoryTransaction.objects.create(
			inventory_item=self.stock,
			transaction_type=InventoryTransaction.Type.OUT,
			source=InventoryTransaction.Source.ORDER,
			quantity="0.500000",
			order=self.paid_order,
		)
		InventoryTransaction.objects.create(
			inventory_item=self.stock,
			transaction_type=InventoryTransaction.Type.REVERSAL,
			source=InventoryTransaction.Source.ORDER,
			quantity="0.100000",
			order=self.cancelled_order,
		)
		self.url = "/api/analytics/dashboard/"

	def dashboard(self, user=None, **params):
		self.client.force_authenticate(user or self.owner_a)
		return self.client.get(self.url, params)

	def test_owner_summary_uses_paid_bills_and_excludes_cancelled_revenue(self):
		response = self.dashboard(period="today")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["metrics"]["collected_revenue"], "115.00")
		self.assertEqual(response.data["metrics"]["total_orders"], 3)
		self.assertEqual(response.data["metrics"]["paid_orders"], 1)
		self.assertEqual(response.data["metrics"]["unpaid_orders"], 2)
		self.assertEqual(response.data["metrics"]["completed_orders"], 1)
		self.assertEqual(response.data["metrics"]["cancelled_orders"], 1)
		self.assertEqual(response.data["metrics"]["average_paid_bill_value"], "115.00")
		self.assertEqual(response.data["metrics"]["paid_bill_count"], 1)
		self.assertEqual(response.data["metrics"]["unpaid_bill_count"], 1)
		self.assertEqual(response.data["metrics"]["unpaid_bill_amount"], "88.00")
		self.assertEqual(response.data["payment_methods"], [{"method": "CASH", "amount": "115.00", "count": 1}])
		self.assertNotIn("customer_phone", response.data)
		self.assertEqual(response.data["currency"], "USD")

	def test_manager_can_access_assigned_restaurant_and_owner_cannot_select_another(self):
		manager_response = self.dashboard(self.manager_a, restaurant=self.restaurant_a.id)
		cross_restaurant = self.dashboard(self.owner_a, restaurant=self.restaurant_b.id)

		self.assertEqual(manager_response.status_code, status.HTTP_200_OK)
		self.assertEqual(manager_response.data["restaurant"]["id"], self.restaurant_a.id)
		self.assertEqual(cross_restaurant.status_code, status.HTTP_404_NOT_FOUND)

	def test_customer_waiter_and_kitchen_cannot_access_business_analytics(self):
		customer_response = self.dashboard(self.customer_a)
		waiter_response = self.dashboard(self.waiter_a)
		self.client.force_authenticate(self.customer_b)
		kitchen = User.objects.create_user("analytics-kitchen-a", password="test-password", role="KITCHEN")
		RestaurantStaff.objects.create(user=kitchen, restaurant=self.restaurant_a, role=User.Role.KITCHEN)
		kitchen_response = self.dashboard(kitchen)

		self.assertEqual(customer_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(waiter_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(kitchen_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_popular_items_aggregate_orders_and_exclude_cancelled_orders(self):
		response = self.dashboard(period="today")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data["popular_items"]), 1)
		self.assertEqual(response.data["popular_items"][0]["name"], "Chicken Momo")
		self.assertEqual(response.data["popular_items"][0]["quantity_sold"], 6)
		self.assertEqual(response.data["popular_items"][0]["item_revenue"], "180.00")

	def test_custom_date_range_filters_data_and_empty_period_has_zero_aov(self):
		yesterday = self.today - timedelta(days=2)
		Bill.objects.filter(id=self.paid_bill.id).update(paid_at=self.start - timedelta(days=3))

		empty = self.dashboard(
			period="custom",
			start=yesterday.isoformat(),
			end=yesterday.isoformat(),
		)
		invalid = self.dashboard(period="custom", start=self.today.isoformat(), end=yesterday.isoformat())

		self.assertEqual(empty.status_code, status.HTTP_200_OK)
		self.assertEqual(empty.data["metrics"]["total_orders"], 0)
		self.assertEqual(empty.data["metrics"]["collected_revenue"], "0.00")
		self.assertEqual(empty.data["metrics"]["average_paid_bill_value"], "0.00")
		self.assertEqual(empty.data["revenue_trend"], [{"date": yesterday.isoformat(), "revenue": "0.00"}])
		self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

	def test_7_day_period_fills_missing_revenue_days_and_inventory_usage_is_net(self):
		response = self.dashboard(period="7d")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data["revenue_trend"]), 7)
		self.assertEqual(response.data["revenue_trend"][-1]["revenue"], "115.00")
		self.assertEqual(response.data["inventory"]["active_item_count"], 1)
		self.assertEqual(response.data["inventory_order_usage"], [{
			"inventory_item_id": self.stock.id,
			"name": "Chicken",
			"unit": "kg",
			"quantity_used": "0.400000",
		}])

	def test_dashboard_is_read_only_and_requires_authentication(self):
		response = self.dashboard()
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.client.force_authenticate(None)
		unauthenticated = self.client.get(self.url)
		self.assertEqual(unauthenticated.status_code, status.HTTP_401_UNAUTHORIZED)
