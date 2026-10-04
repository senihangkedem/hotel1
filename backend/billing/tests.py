from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import InventoryItem, InventoryTransaction
from menu.models import MenuItem, MenuItemIngredient
from orders.models import Order, OrderItem
from restaurants.models import Restaurant, RestaurantStaff

from .models import Bill


User = get_user_model()


class BillingAPITests(APITestCase):
    def setUp(self):
        self.owner_a = User.objects.create_user("bill-owner-a", password="test-password", role="OWNER")
        self.owner_b = User.objects.create_user("bill-owner-b", password="test-password", role="OWNER")
        self.manager_a = User.objects.create_user("bill-manager-a", password="test-password", role="MANAGER")
        self.waiter_a = User.objects.create_user("bill-waiter-a", password="test-password", role="WAITER")
        self.kitchen_a = User.objects.create_user("bill-kitchen-a", password="test-password", role="KITCHEN")
        self.customer_a = User.objects.create_user("bill-customer-a", password="test-password", role="CUSTOMER")
        self.customer_b = User.objects.create_user("bill-customer-b", password="test-password", role="CUSTOMER")
        self.restaurant_a = Restaurant.objects.create(
            owner=self.owner_a,
            name="Billing A",
            address="1 Bill Street",
            tax_rate="10.00",
            service_charge_rate="5.00",
        )
        self.restaurant_b = Restaurant.objects.create(
            owner=self.owner_b,
            name="Billing B",
            address="2 Bill Street",
        )
        RestaurantStaff.objects.create(user=self.manager_a, restaurant=self.restaurant_a, role=User.Role.MANAGER)
        RestaurantStaff.objects.create(user=self.waiter_a, restaurant=self.restaurant_a, role=User.Role.WAITER)
        RestaurantStaff.objects.create(user=self.kitchen_a, restaurant=self.restaurant_a, role=User.Role.KITCHEN)

        self.menu_item_a = MenuItem.objects.create(
            restaurant=self.restaurant_a,
            name="Billing Momo",
            price="50.00",
        )
        self.menu_item_b = MenuItem.objects.create(
            restaurant=self.restaurant_b,
            name="Other Momo",
            price="25.00",
        )
        self.stock = InventoryItem.objects.create(
            restaurant=self.restaurant_a,
            name="Billing Chicken",
            unit=InventoryItem.Unit.KILOGRAM,
            quantity_on_hand="3.000000",
        )
        MenuItemIngredient.objects.create(
            menu_item=self.menu_item_a,
            inventory_item=self.stock,
            quantity_required="0.100000",
            unit="kg",
        )
        self.order_a = Order.objects.create(
            restaurant=self.restaurant_a,
            customer=self.customer_a,
            status=Order.Status.SERVED,
            total_amount="100.00",
        )
        self.order_b = Order.objects.create(
            restaurant=self.restaurant_b,
            customer=self.customer_b,
            status=Order.Status.SERVED,
            total_amount="25.00",
        )
        OrderItem.objects.create(
            order=self.order_a,
            menu_item=self.menu_item_a,
            quantity=2,
            unit_price="50.00",
            subtotal="100.00",
        )
        OrderItem.objects.create(
            order=self.order_b,
            menu_item=self.menu_item_b,
            quantity=1,
            unit_price="25.00",
            subtotal="25.00",
        )
        self.bills_url = "/api/billing/bills/"

    def create_payload(self, order=None, **extra):
        payload = {"order": (order or self.order_a).id}
        payload.update(extra)
        return payload

    def create_bill(self, actor=None, order=None, **extra):
        self.client.force_authenticate(actor or self.owner_a)
        return self.client.post(self.bills_url, self.create_payload(order, **extra), format="json")

    def test_manager_can_create_bill_from_server_order_totals_and_snapshot_lines(self):
        response = self.create_bill(self.manager_a, subtotal="1.00", total_amount="0.01")

        self.stock.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["subtotal"], "100.00")
        self.assertEqual(response.data["tax_amount"], "10.00")
        self.assertEqual(response.data["service_charge_amount"], "5.00")
        self.assertEqual(response.data["total_amount"], "115.00")
        self.assertEqual(response.data["lines"][0]["item_name"], "Billing Momo")
        self.assertEqual(self.stock.quantity_on_hand, Decimal("3.000000"))
        self.assertFalse(InventoryTransaction.objects.filter(order=self.order_a).exists())

    def test_customer_cannot_create_manage_or_pay_bills(self):
        self.client.force_authenticate(self.customer_a)
        create_response = self.client.post(self.bills_url, self.create_payload(), format="json")
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

        bill_response = self.create_bill()
        bill_id = bill_response.data["id"]
        self.client.force_authenticate(self.customer_a)
        pay_response = self.client.post(
            f"{self.bills_url}{bill_id}/pay/",
            {"payment_method": Bill.PaymentMethod.CASH},
            format="json",
        )
        change_response = self.client.patch(
            f"{self.bills_url}{bill_id}/",
            {"discount_value": "5.00"},
            format="json",
        )
        self.assertEqual(pay_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(change_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_restaurant_creation_and_detail_access_are_rejected(self):
        self.client.force_authenticate(self.owner_a)
        other_bill = self.client.post(
            self.bills_url,
            self.create_payload(self.order_b),
            format="json",
        )
        self.assertEqual(other_bill.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.owner_b)
        created = self.client.post(self.bills_url, self.create_payload(self.order_b), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(self.owner_a)
        detail = self.client.get(f"{self.bills_url}{created.data['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_one_bill_per_order_and_only_customer_owned_bill_is_visible(self):
        created = self.create_bill()
        duplicate = self.create_bill()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(self.customer_a)
        visible = self.client.get(self.bills_url)
        hidden = self.client.get(f"{self.bills_url}{created.data['id']}/")
        self.assertEqual(visible.status_code, status.HTTP_200_OK)
        self.assertEqual(len(visible.data), 1)
        self.assertEqual(hidden.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.customer_b)
        other_customer = self.client.get(f"{self.bills_url}{created.data['id']}/")
        self.assertEqual(other_customer.status_code, status.HTTP_404_NOT_FOUND)

    def test_discount_validation_and_percentage_calculation(self):
        self.client.force_authenticate(self.owner_a)
        too_high_percentage = self.client.post(
            self.bills_url,
            self.create_payload(discount_type=Bill.DiscountType.PERCENTAGE, discount_value="100.01"),
            format="json",
        )
        too_high_fixed = self.client.post(
            self.bills_url,
            self.create_payload(discount_type=Bill.DiscountType.FIXED, discount_value="100.01"),
            format="json",
        )
        negative = self.client.post(
            self.bills_url,
            self.create_payload(discount_type=Bill.DiscountType.FIXED, discount_value="-1.00"),
            format="json",
        )
        self.assertEqual(too_high_percentage.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(too_high_fixed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(negative.status_code, status.HTTP_400_BAD_REQUEST)

        bill = self.client.post(
            self.bills_url,
            self.create_payload(discount_type=Bill.DiscountType.PERCENTAGE, discount_value="10.00"),
            format="json",
        )
        self.assertEqual(bill.status_code, status.HTTP_201_CREATED)
        self.assertEqual(bill.data["discount_amount"], "10.00")
        self.assertEqual(bill.data["tax_amount"], "9.00")
        self.assertEqual(bill.data["service_charge_amount"], "4.50")
        self.assertEqual(bill.data["total_amount"], "103.50")

    def test_restaurant_tax_and_service_rates_are_configurable_and_snapshotted(self):
        self.client.force_authenticate(self.manager_a)
        settings_url = f"/api/billing/settings/{self.restaurant_a.id}/"
        settings = self.client.patch(
            settings_url,
            {"tax_rate": "8.25", "service_charge_rate": "0.00"},
            format="json",
        )
        self.assertEqual(settings.status_code, status.HTTP_200_OK)

        bill = self.client.post(self.bills_url, self.create_payload(), format="json")
        self.assertEqual(bill.status_code, status.HTTP_201_CREATED)
        self.assertEqual(bill.data["tax_rate"], "8.25")
        self.assertEqual(bill.data["tax_amount"], "8.25")
        self.assertEqual(bill.data["service_charge_amount"], "0.00")
        self.assertEqual(bill.data["total_amount"], "108.25")

    def test_waiter_can_read_bills_but_cannot_create_or_mark_paid(self):
        bill = self.create_bill()
        self.client.force_authenticate(self.waiter_a)
        read_response = self.client.get(f"{self.bills_url}{bill.data['id']}/")
        create_response = self.client.post(self.bills_url, self.create_payload(), format="json")
        pay_response = self.client.post(
            f"{self.bills_url}{bill.data['id']}/pay/",
            {"payment_method": Bill.PaymentMethod.CASH},
            format="json",
        )
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(pay_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_payment_marks_bill_paid_syncs_order_and_rejects_duplicates(self):
        bill = self.create_bill()
        bill_id = bill.data["id"]
        self.client.force_authenticate(self.manager_a)
        payment = self.client.post(
            f"{self.bills_url}{bill_id}/pay/",
            {"payment_method": Bill.PaymentMethod.CASH},
            format="json",
        )
        duplicate = self.client.post(
            f"{self.bills_url}{bill_id}/pay/",
            {"payment_method": Bill.PaymentMethod.CARD},
            format="json",
        )
        changed_paid_bill = self.client.patch(
            f"{self.bills_url}{bill_id}/",
            {"discount_value": "1.00"},
            format="json",
        )

        self.order_a.refresh_from_db()
        self.assertEqual(payment.status_code, status.HTTP_200_OK)
        self.assertEqual(payment.data["payment_status"], Order.PaymentStatus.PAID)
        self.assertEqual(payment.data["payment_method"], Bill.PaymentMethod.CASH)
        self.assertEqual(payment.data["paid_by_name"], self.manager_a.username)
        self.assertIsNotNone(payment.data["paid_at"])
        self.assertEqual(self.order_a.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(changed_paid_bill.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kitchen_cannot_read_bills_and_tax_settings_are_manager_scoped(self):
        bill = self.create_bill()
        self.client.force_authenticate(self.kitchen_a)
        bill_response = self.client.get(f"{self.bills_url}{bill.data['id']}/")
        settings_response = self.client.patch(
            f"/api/billing/settings/{self.restaurant_a.id}/",
            {"tax_rate": "100.00"},
            format="json",
        )
        self.assertEqual(bill_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(settings_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_paid_bill_order_cannot_be_cancelled_without_refund_support(self):
        bill = self.create_bill()
        self.client.force_authenticate(self.manager_a)
        paid = self.client.post(
            f"{self.bills_url}{bill.data['id']}/pay/",
            {"payment_method": Bill.PaymentMethod.CASH},
            format="json",
        )
        self.assertEqual(paid.status_code, status.HTTP_200_OK)

        cancelled = self.client.post(
            f"/api/orders/orders/{self.order_a.id}/transition/",
            {"status": Order.Status.CANCELLED},
            format="json",
        )

        self.order_a.refresh_from_db()
        self.assertEqual(cancelled.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.order_a.status, Order.Status.SERVED)
