from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from billing.models import Bill
from config.asgi import application
from menu.models import Category, MenuItem
from restaurants.models import Restaurant, RestaurantTable

from .models import Order

User = get_user_model()


class OrderSecurityTests(APITestCase):
    def setUp(self):
        self.owner_a = User.objects.create_user(
            username="owner-a",
            password="test-password",
            role="OWNER",
        )
        self.owner_b = User.objects.create_user(
            username="owner-b",
            password="test-password",
            role="OWNER",
        )
        self.customer_a = User.objects.create_user(
            username="customer-a",
            password="test-password",
            role="CUSTOMER",
        )
        self.customer_b = User.objects.create_user(
            username="customer-b",
            password="test-password",
            role="CUSTOMER",
        )
        self.superuser = User.objects.create_superuser(
            username="admin",
            password="test-password",
        )

        self.restaurant_a = Restaurant.objects.create(
            owner=self.owner_a,
            name="Restaurant A",
            address="Address A",
        )
        self.restaurant_b = Restaurant.objects.create(
            owner=self.owner_b,
            name="Restaurant B",
            address="Address B",
        )

        self.table_a = RestaurantTable.objects.create(
            restaurant=self.restaurant_a,
            table_number=1,
            capacity=4,
        )
        self.table_b = RestaurantTable.objects.create(
            restaurant=self.restaurant_b,
            table_number=1,
            capacity=4,
        )

        self.category_a = Category.objects.create(
            restaurant=self.restaurant_a,
            name="Category A",
        )
        self.category_b = Category.objects.create(
            restaurant=self.restaurant_b,
            name="Category B",
        )

        self.menu_item_a = MenuItem.objects.create(
            restaurant=self.restaurant_a,
            category=self.category_a,
            name="Item A",
            price="12.50",
            is_available=True,
        )
        self.menu_item_b = MenuItem.objects.create(
            restaurant=self.restaurant_b,
            category=self.category_b,
            name="Item B",
            price="20.00",
            is_available=True,
        )

        self.order_a = Order.objects.create(
            restaurant=self.restaurant_a,
            table=self.table_a,
            customer=self.customer_a,
            status=Order.Status.PENDING,
            payment_status=Order.PaymentStatus.UNPAID,
            total_amount="12.50",
        )
        self.order_b = Order.objects.create(
            restaurant=self.restaurant_b,
            table=self.table_b,
            customer=self.customer_b,
            status=Order.Status.PENDING,
            payment_status=Order.PaymentStatus.UNPAID,
            total_amount="20.00",
        )

    def test_owner_cannot_list_or_edit_other_owners_orders(self):
        self.client.force_authenticate(self.owner_a)

        list_response = self.client.get("/api/orders/orders/")
        detail_response = self.client.get(f"/api/orders/orders/{self.order_b.id}/")
        patch_response = self.client.patch(
            f"/api/orders/orders/{self.order_b.id}/",
            {"notes": "tampered"},
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(patch_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_cannot_modify_other_customers_order(self):
        self.client.force_authenticate(self.customer_a)

        response = self.client.patch(
            f"/api/orders/orders/{self.order_b.id}/",
            {"notes": "tampered"},
            format="json",
        )

        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_owner_cannot_create_order_for_other_restaurant_tables_or_items(self):
        self.client.force_authenticate(self.owner_a)
        payload = {
            "restaurant": self.restaurant_a.id,
            "table": self.table_b.id,
            "customer_name": "Guest",
            "customer_phone": "9800000000",
            "notes": "bad order",
            "items": [
                {
                    "menu_item": self.menu_item_b.id,
                    "quantity": 1,
                }
            ],
        }

        response = self.client.post("/api/orders/orders/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_creation_rejects_unavailable_item_and_invalid_quantity(self):
        self.client.force_authenticate(self.customer_a)

        self.menu_item_a.is_available = False
        self.menu_item_a.save(update_fields=["is_available"])

        unavailable_response = self.client.post(
            "/api/orders/orders/",
            {
                "restaurant": self.restaurant_a.id,
                "table": self.table_a.id,
                "customer_name": "Guest",
                "customer_phone": "9800000000",
                "items": [{"menu_item": self.menu_item_a.id, "quantity": 1}],
            },
            format="json",
        )

        invalid_quantity_response = self.client.post(
            "/api/orders/orders/",
            {
                "restaurant": self.restaurant_a.id,
                "table": self.table_a.id,
                "customer_name": "Guest",
                "customer_phone": "9800000000",
                "items": [{"menu_item": self.menu_item_a.id, "quantity": 0}],
            },
            format="json",
        )

        self.assertEqual(unavailable_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_quantity_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_creation_rejects_empty_items_and_price_tampering(self):
        self.client.force_authenticate(self.customer_a)

        empty_items_response = self.client.post(
            "/api/orders/orders/",
            {
                "restaurant": self.restaurant_a.id,
                "table": self.table_a.id,
                "customer_name": "Guest",
                "customer_phone": "9800000000",
                "items": [],
            },
            format="json",
        )

        tampered_response = self.client.post(
            "/api/orders/orders/",
            {
                "restaurant": self.restaurant_a.id,
                "table": self.table_a.id,
                "customer_name": "Guest",
                "customer_phone": "9800000000",
                "items": [{
                    "menu_item": self.menu_item_a.id,
                    "quantity": 2,
                    "unit_price": "999.99",
                    "subtotal": "999.99",
                }],
            },
            format="json",
        )

        self.assertEqual(empty_items_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(tampered_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(tampered_response.data["total_amount"]), 25.0)

    def test_superuser_still_has_admin_access(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.get("/api/orders/orders/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)


class OrderWebSocketSecurityTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner-ws",
            password="test-password",
            role="OWNER",
        )
        self.manager = User.objects.create_user(
            username="manager-ws",
            password="test-password",
            role="MANAGER",
        )
        self.other_owner = User.objects.create_user(
            username="other-owner",
            password="test-password",
            role="OWNER",
        )

        self.restaurant = Restaurant.objects.create(
            owner=self.owner,
            name="Realtime Restaurant",
            address="Some street",
        )
        self.other_restaurant = Restaurant.objects.create(
            owner=self.other_owner,
            name="Other Restaurant",
            address="Other street",
        )
        self.restaurant.staff_memberships.create(
            user=self.manager,
            role="MANAGER",
            is_active=True,
        )

        self.table = RestaurantTable.objects.create(
            restaurant=self.restaurant,
            table_number=1,
            capacity=4,
        )

        self.category = Category.objects.create(
            restaurant=self.restaurant,
            name="Lunch",
        )
        self.menu_item = MenuItem.objects.create(
            restaurant=self.restaurant,
            category=self.category,
            name="Burger",
            price="9.99",
            is_available=True,
        )

    async def test_unauthenticated_socket_is_rejected(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/restaurants/{self.restaurant.id}/",
            headers=[(b"origin", b"http://localhost")],
        )
        connected = await communicator.connect()
        self.assertFalse(connected[0])

    async def test_authorized_staff_socket_is_connected(self):
        token = str(AccessToken.for_user(self.manager))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/restaurants/{self.restaurant.id}/?token={token}",
            headers=[(b"origin", b"http://localhost")],
        )
        connected = await communicator.connect()
        self.assertTrue(connected[0])
        await communicator.disconnect()

    async def test_unauthorized_restaurant_socket_is_rejected(self):
        token = str(AccessToken.for_user(self.owner))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/restaurants/{self.other_restaurant.id}/?token={token}",
            headers=[(b"origin", b"http://localhost")],
        )
        connected = await communicator.connect()
        self.assertFalse(connected[0])

class OrderWebSocketEventDeliveryTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner_a = User.objects.create_user("owner-event-a", password="test-password", role="OWNER")
        self.owner_b = User.objects.create_user("owner-event-b", password="test-password", role="OWNER")
        self.manager_a = User.objects.create_user("manager-event-a", password="test-password", role="MANAGER")
        self.manager_b = User.objects.create_user("manager-event-b", password="test-password", role="MANAGER")
        self.customer = User.objects.create_user("customer-event", password="test-password", role="CUSTOMER")

        self.restaurant_a = Restaurant.objects.create(
            owner=self.owner_a,
            name="Realtime A",
            address="1 Event Street",
        )
        self.restaurant_b = Restaurant.objects.create(
            owner=self.owner_b,
            name="Realtime B",
            address="2 Event Street",
        )
        self.restaurant_a.staff_memberships.create(user=self.manager_a, role="MANAGER", is_active=True)
        self.restaurant_b.staff_memberships.create(user=self.manager_b, role="MANAGER", is_active=True)

        self.table_a = RestaurantTable.objects.create(restaurant=self.restaurant_a, table_number=1)
        self.table_b = RestaurantTable.objects.create(restaurant=self.restaurant_b, table_number=1)
        self.item_a = MenuItem.objects.create(
            restaurant=self.restaurant_a,
            category=Category.objects.create(restaurant=self.restaurant_a, name="A Menu"),
            name="A Dish",
            price="9.99",
            is_available=True,
        )
        self.item_b = MenuItem.objects.create(
            restaurant=self.restaurant_b,
            category=Category.objects.create(restaurant=self.restaurant_b, name="B Menu"),
            name="B Dish",
            price="12.00",
            is_available=True,
        )

    async def connect_staff(self, user, restaurant):
        token = str(AccessToken.for_user(user))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/restaurants/{restaurant.id}/?token={token}",
            headers=[(b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        return communicator

    async def request_as(self, user, method, path, data):
        def make_request():
            client = APIClient()
            client.force_authenticate(user)
            return getattr(client, method)(path, data, format="json")

        return await sync_to_async(make_request, thread_sensitive=True)()

    async def assert_no_event(self, communicator):
        self.assertTrue(await communicator.receive_nothing(timeout=0.2))

    async def test_staff_receive_only_their_restaurant_order_events(self):
        socket_a = await self.connect_staff(self.manager_a, self.restaurant_a)
        socket_b = await self.connect_staff(self.manager_b, self.restaurant_b)

        try:
            order_a_response = await self.request_as(
                self.manager_a,
                "post",
                "/api/orders/orders/",
                {
                    "restaurant": self.restaurant_a.id,
                    "table": self.table_a.id,
                    "customer_name": "Private Guest",
                    "customer_phone": "5551234567",
                    "items": [{"menu_item": self.item_a.id, "quantity": 1}],
                },
            )
            self.assertEqual(order_a_response.status_code, status.HTTP_201_CREATED)
            order_id = order_a_response.data["id"]

            created_event = await socket_a.receive_json_from(timeout=2)
            self.assertEqual(created_event["event"], "order.created")
            self.assertEqual(created_event["order_id"], order_id)
            self.assertEqual(created_event["restaurant_id"], self.restaurant_a.id)
            self.assertEqual(created_event["status"], Order.Status.PENDING)
            self.assertEqual(created_event["payment_status"], Order.PaymentStatus.UNPAID)
            for private_field in ("customer_name", "customer_phone", "customer_id", "items"):
                self.assertNotIn(private_field, created_event)
            await self.assert_no_event(socket_b)

            transition_response = await self.request_as(
                self.manager_a,
                "post",
                f"/api/orders/orders/{order_id}/transition/",
                {"status": Order.Status.CONFIRMED},
            )
            self.assertEqual(transition_response.status_code, status.HTTP_200_OK)
            status_event = await socket_a.receive_json_from(timeout=2)
            self.assertEqual(status_event["event"], "order.status_changed")
            self.assertEqual(status_event["order_id"], order_id)
            self.assertEqual(status_event["status"], Order.Status.CONFIRMED)
            await self.assert_no_event(socket_b)

            bill_response = await self.request_as(
                self.manager_a,
                "post",
                "/api/billing/bills/",
                {"order": order_id},
            )
            self.assertEqual(bill_response.status_code, status.HTTP_201_CREATED)
            payment_response = await self.request_as(
                self.manager_a,
                "post",
                f"/api/billing/bills/{bill_response.data['id']}/pay/",
                {"payment_method": Bill.PaymentMethod.CASH},
            )
            self.assertEqual(payment_response.status_code, status.HTTP_200_OK)
            payment_event = await socket_a.receive_json_from(timeout=2)
            self.assertEqual(payment_event["event"], "order.payment_status_changed")
            self.assertEqual(payment_event["order_id"], order_id)
            self.assertEqual(payment_event["payment_status"], Order.PaymentStatus.PAID)
            await self.assert_no_event(socket_b)

            order_b_response = await self.request_as(
                self.manager_b,
                "post",
                "/api/orders/orders/",
                {
                    "restaurant": self.restaurant_b.id,
                    "table": self.table_b.id,
                    "items": [{"menu_item": self.item_b.id, "quantity": 1}],
                },
            )
            self.assertEqual(order_b_response.status_code, status.HTTP_201_CREATED)
            event_b = await socket_b.receive_json_from(timeout=2)
            self.assertEqual(event_b["event"], "order.created")
            self.assertEqual(event_b["order_id"], order_b_response.data["id"])
            self.assertEqual(event_b["restaurant_id"], self.restaurant_b.id)
            await self.assert_no_event(socket_a)
        finally:
            await socket_a.disconnect()
            await socket_b.disconnect()

    async def test_order_event_is_not_sent_when_transaction_rolls_back(self):
        socket = await self.connect_staff(self.manager_a, self.restaurant_a)

        def create_order_then_rollback():
            client = APIClient()
            client.force_authenticate(self.manager_a)
            with transaction.atomic():
                response = client.post(
                    "/api/orders/orders/",
                    {
                        "restaurant": self.restaurant_a.id,
                        "table": self.table_a.id,
                        "items": [{"menu_item": self.item_a.id, "quantity": 1}],
                    },
                    format="json",
                )
                if response.status_code != status.HTTP_201_CREATED:
                    raise AssertionError(response.data)
                created_order_id = response.data["id"]
                raise RuntimeError(created_order_id)

        try:
            with self.assertRaises(RuntimeError) as error:
                await sync_to_async(create_order_then_rollback, thread_sensitive=True)()
            rolled_back_order_id = int(str(error.exception))
            self.assertFalse(await sync_to_async(Order.objects.filter(id=rolled_back_order_id).exists)())
            await self.assert_no_event(socket)
        finally:
            await socket.disconnect()
