from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from menu.models import Category, MenuItem
from orders.models import Order

from .models import Restaurant, RestaurantStaff, RestaurantTable


User = get_user_model()


class RestaurantOwnershipTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="owner",
			password="test-password",
			role="OWNER",
		)
		self.other_owner = User.objects.create_user(
			username="other-owner",
			password="test-password",
			role="OWNER",
		)
		self.customer = User.objects.create_user(
			username="customer",
			password="test-password",
			role="CUSTOMER",
		)
		self.superuser = User.objects.create_superuser(
			username="superuser",
			password="test-password",
		)
		self.owner_restaurant = Restaurant.objects.create(
			owner=self.owner,
			name="Owner Restaurant",
			address="1 Owner Street",
		)
		self.other_restaurant = Restaurant.objects.create(
			owner=self.other_owner,
			name="Other Restaurant",
			address="2 Other Street",
		)
		self.url = "/api/restaurants/restaurants/"

	def restaurant_payload(self, name="New Restaurant"):
		return {
			"owner": self.other_owner.id,
			"name": name,
			"description": "A test restaurant",
			"address": "3 New Street",
		}

	def test_owner_can_create_restaurant_for_themselves(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(self.url, self.restaurant_payload())

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		created = Restaurant.objects.get(id=response.data["id"])
		self.assertEqual(created.owner, self.owner)
		self.assertEqual(response.data["owner"], self.owner.id)

	def test_owner_sees_only_their_restaurants(self):
		self.client.force_authenticate(self.owner)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{item["id"] for item in response.data},
			{self.owner_restaurant.id},
		)

	def test_owner_cannot_update_or_delete_another_owners_restaurant(self):
		self.client.force_authenticate(self.owner)
		detail_url = f"{self.url}{self.other_restaurant.id}/"

		update_response = self.client.patch(
			detail_url,
			{"name": "Unauthorized Update"},
		)
		delete_response = self.client.delete(detail_url)

		self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
		self.other_restaurant.refresh_from_db()
		self.assertEqual(self.other_restaurant.name, "Other Restaurant")

	def test_owner_cannot_reassign_their_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.patch(
			f"{self.url}{self.owner_restaurant.id}/",
			{"owner": self.other_owner.id},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.owner_restaurant.refresh_from_db()
		self.assertEqual(self.owner_restaurant.owner, self.owner)

	def test_superuser_can_access_all_restaurants(self):
		self.client.force_authenticate(self.superuser)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{item["id"] for item in response.data},
			{self.owner_restaurant.id, self.other_restaurant.id},
		)

	def test_customer_cannot_manage_restaurants(self):
		self.client.force_authenticate(self.customer)

		create_response = self.client.post(self.url, self.restaurant_payload())
		update_response = self.client.patch(
			f"{self.url}{self.owner_restaurant.id}/",
			{"name": "Unauthorized Update"},
		)

		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)


class RestaurantTableSecurityTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="table-owner",
			password="test-password",
			role="OWNER",
		)
		self.other_owner = User.objects.create_user(
			username="table-other-owner",
			password="test-password",
			role="OWNER",
		)
		self.customer = User.objects.create_user(
			username="table-customer",
			password="test-password",
			role="CUSTOMER",
		)
		self.superuser = User.objects.create_superuser(
			username="table-superuser",
			password="test-password",
		)
		self.restaurant = Restaurant.objects.create(
			owner=self.owner,
			name="Table Owner Restaurant",
			address="1 Table Street",
		)
		self.other_restaurant = Restaurant.objects.create(
			owner=self.other_owner,
			name="Table Other Restaurant",
			address="2 Table Street",
		)
		self.other_table = RestaurantTable.objects.create(
			restaurant=self.other_restaurant,
			table_number=1,
			capacity=4,
		)
		self.url = "/api/restaurants/tables/"

	def table_payload(self, restaurant=None, table_number=2, capacity=4):
		return {
			"restaurant": (restaurant or self.restaurant).id,
			"table_number": table_number,
			"capacity": capacity,
			"is_active": True,
		}

	def test_owner_can_create_table_in_their_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(self.url, self.table_payload())

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["restaurant"], self.restaurant.id)

	def test_owner_cannot_create_table_in_another_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(
			self.url,
			self.table_payload(self.other_restaurant, table_number=2),
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_owner_sees_only_their_tables(self):
		RestaurantTable.objects.create(
			restaurant=self.restaurant,
			table_number=1,
			capacity=4,
		)
		self.client.force_authenticate(self.owner)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{item["restaurant"] for item in response.data},
			{self.restaurant.id},
		)

	def test_owner_cannot_update_or_delete_another_owners_table(self):
		self.client.force_authenticate(self.owner)
		detail_url = f"{self.url}{self.other_table.id}/"

		update_response = self.client.patch(detail_url, {"capacity": 8})
		delete_response = self.client.delete(detail_url)

		self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertTrue(RestaurantTable.objects.filter(id=self.other_table.id).exists())

	def test_customer_can_read_tables_but_cannot_manage_them(self):
		self.client.force_authenticate(self.customer)

		create_response = self.client.post(self.url, self.table_payload())
		list_response = self.client.get(self.url)

		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{table["id"] for table in list_response.data},
			{self.other_table.id},
		)

	def test_superuser_can_access_all_tables(self):
		self.client.force_authenticate(self.superuser)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)
		self.assertEqual(response.data[0]["restaurant"], self.other_restaurant.id)

	def test_table_number_and_capacity_must_be_positive(self):
		self.client.force_authenticate(self.owner)

		zero_capacity = self.client.post(
			self.url,
			self.table_payload(table_number=2, capacity=0),
		)
		zero_table_number = self.client.post(
			self.url,
			self.table_payload(table_number=0, capacity=4),
		)

		self.assertEqual(zero_capacity.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(zero_table_number.status_code, status.HTTP_400_BAD_REQUEST)


class RestaurantStaffManagementTests(APITestCase):
	def setUp(self):
		self.owner_a = User.objects.create_user(
			username="staff-owner-a",
			password="test-password",
			role="OWNER",
		)
		self.owner_b = User.objects.create_user(
			username="staff-owner-b",
			password="test-password",
			role="OWNER",
		)
		self.customer = User.objects.create_user(
			username="staff-customer",
			password="test-password",
			role="CUSTOMER",
		)
		self.manager = User.objects.create_user(
			username="restaurant-manager",
			password="test-password",
			role="MANAGER",
		)
		self.restaurant_a = Restaurant.objects.create(
			owner=self.owner_a,
			name="Staff Restaurant A",
			address="10 Restaurant A Road",
		)
		self.restaurant_b = Restaurant.objects.create(
			owner=self.owner_b,
			name="Staff Restaurant B",
			address="20 Restaurant B Road",
		)
		self.membership_a = RestaurantStaff.objects.create(
			user=self.manager,
			restaurant=self.restaurant_a,
			role=User.Role.MANAGER,
		)
		self.table_a = RestaurantTable.objects.create(
			restaurant=self.restaurant_a,
			table_number=1,
		)
		self.table_b = RestaurantTable.objects.create(
			restaurant=self.restaurant_b,
			table_number=1,
		)
		self.category_a = Category.objects.create(
			restaurant=self.restaurant_a,
			name="A mains",
		)
		self.category_b = Category.objects.create(
			restaurant=self.restaurant_b,
			name="B mains",
		)
		self.item_a = MenuItem.objects.create(
			restaurant=self.restaurant_a,
			category=self.category_a,
			name="A dish",
			price="12.00",
		)
		self.item_b = MenuItem.objects.create(
			restaurant=self.restaurant_b,
			category=self.category_b,
			name="B dish",
			price="18.00",
		)
		self.order_a = Order.objects.create(
			restaurant=self.restaurant_a,
			table=self.table_a,
			customer=self.customer,
			total_amount="12.00",
		)
		self.order_b = Order.objects.create(
			restaurant=self.restaurant_b,
			table=self.table_b,
			customer=self.customer,
			total_amount="18.00",
		)
		self.staff_url = "/api/restaurants/staff/"

	def test_owner_lists_only_staff_from_their_restaurants(self):
		other_user = User.objects.create_user(
			username="other-restaurant-manager",
			password="test-password",
			role="MANAGER",
		)
		other_membership = RestaurantStaff.objects.create(
			user=other_user,
			restaurant=self.restaurant_b,
			role=User.Role.MANAGER,
		)
		self.client.force_authenticate(self.owner_a)

		response = self.client.get(self.staff_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in response.data}, {self.membership_a.id})
		self.assertNotIn(other_membership.id, {row["id"] for row in response.data})

	def test_owner_can_create_staff_with_hashed_password(self):
		self.client.force_authenticate(self.owner_a)

		response = self.client.post(
			self.staff_url,
			{
				"restaurant": self.restaurant_a.id,
				"username": "new-kitchen-user",
				"email": "kitchen@example.test",
				"phone": "555-0100",
				"role": User.Role.KITCHEN,
				"password": "Good-Passphrase-493!",
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		staff_user = User.objects.get(username="new-kitchen-user")
		self.assertTrue(staff_user.check_password("Good-Passphrase-493!"))
		self.assertNotIn("password", response.data)
		self.assertEqual(response.data["restaurant"], self.restaurant_a.id)
		self.assertEqual(response.data["role"], User.Role.KITCHEN)

	def test_customer_cannot_list_or_add_staff_and_owner_cannot_assign_owner_role(self):
		self.client.force_authenticate(self.customer)
		list_response = self.client.get(self.staff_url)
		create_response = self.client.post(
			self.staff_url,
			{
				"restaurant": self.restaurant_a.id,
				"username": "customer-created-staff",
				"role": User.Role.WAITER,
				"password": "Good-Passphrase-493!",
			},
			format="json",
		)
		self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(self.owner_a)
		owner_role_response = self.client.post(
			self.staff_url,
			{
				"restaurant": self.restaurant_a.id,
				"username": "attempted-owner",
				"role": User.Role.OWNER,
				"password": "Good-Passphrase-493!",
			},
			format="json",
		)
		self.assertEqual(owner_role_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertFalse(User.objects.filter(username="attempted-owner").exists())

	def test_owner_cannot_change_staff_in_another_restaurant(self):
		other_user = User.objects.create_user(
			username="isolated-manager",
			password="test-password",
			role="MANAGER",
		)
		other_membership = RestaurantStaff.objects.create(
			user=other_user,
			restaurant=self.restaurant_b,
			role=User.Role.MANAGER,
		)
		self.client.force_authenticate(self.manager)
		staff_update = self.client.patch(
			f"{self.staff_url}{other_membership.id}/",
			{"role": User.Role.WAITER},
			format="json",
		)
		self.assertEqual(staff_update.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(self.owner_a)

		response = self.client.patch(
			f"{self.staff_url}{other_membership.id}/",
			{"role": User.Role.WAITER},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		other_membership.refresh_from_db()
		self.assertEqual(other_membership.role, User.Role.MANAGER)

	def test_staff_cannot_change_own_role_and_deactivation_is_soft(self):
		self.client.force_authenticate(self.manager)
		self_change_response = self.client.patch(
			f"{self.staff_url}{self.membership_a.id}/",
			{"role": User.Role.OWNER},
			format="json",
		)
		self.assertEqual(self_change_response.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(self.owner_a)
		deactivate_response = self.client.delete(f"{self.staff_url}{self.membership_a.id}/")
		self.assertEqual(deactivate_response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertTrue(RestaurantStaff.objects.filter(id=self.membership_a.id).exists())
		self.membership_a.refresh_from_db()
		self.assertFalse(self.membership_a.is_active)
		self.assertTrue(Order.objects.filter(id=self.order_a.id).exists())

		self.client.force_authenticate(self.manager)
		self.assertEqual(self.client.get("/api/restaurants/tables/").status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(self.client.get("/api/restaurants/staff/").status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(self.client.get("/api/orders/orders/").data, [])

	def test_active_staff_access_only_their_restaurant_orders_and_menu(self):
		self.client.force_authenticate(self.manager)

		orders_response = self.client.get("/api/orders/orders/")
		menu_response = self.client.get("/api/menu/items/")
		other_order_response = self.client.get(f"/api/orders/orders/{self.order_b.id}/")
		other_item_response = self.client.patch(
			f"/api/menu/items/{self.item_b.id}/",
			{"name": "Tampered dish"},
			format="json",
		)

		self.assertEqual(orders_response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in orders_response.data}, {self.order_a.id})
		self.assertEqual(menu_response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in menu_response.data}, {self.item_a.id})
		self.assertEqual(other_order_response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(other_item_response.status_code, status.HTTP_404_NOT_FOUND)
		staff_order_update = self.client.patch(
			f"/api/orders/orders/{self.order_a.id}/",
			{"notes": "staff edit"},
			format="json",
		)
		self.assertEqual(staff_order_update.status_code, status.HTTP_403_FORBIDDEN)

	def test_staff_cannot_read_or_manage_tables_for_another_restaurant(self):
		self.client.force_authenticate(self.manager)

		list_response = self.client.get("/api/restaurants/tables/")
		other_table_response = self.client.patch(
			f"/api/restaurants/tables/{self.table_b.id}/",
			{"capacity": 8},
			format="json",
		)

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in list_response.data}, {self.table_a.id})
		self.assertEqual(other_table_response.status_code, status.HTTP_404_NOT_FOUND)

	def test_current_user_returns_only_active_restaurant_memberships(self):
		self.client.force_authenticate(self.manager)

		response = self.client.get("/api/auth/me/")

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			response.data["staff_memberships"],
			[{
				"restaurant": self.restaurant_a.id,
				"restaurant_name": self.restaurant_a.name,
				"role": User.Role.MANAGER,
			}],
		)
		self.membership_a.is_active = False
		self.membership_a.save(update_fields=["is_active"])

		inactive_response = self.client.get("/api/auth/me/")

		self.assertEqual(inactive_response.data["staff_memberships"], [])

	def test_manager_can_manage_same_restaurant_menu_but_not_other_restaurants(self):
		self.client.force_authenticate(self.manager)

		own_update = self.client.patch(
			f"/api/menu/items/{self.item_a.id}/",
			{"name": "Updated A dish"},
			format="json",
		)
		other_update = self.client.patch(
			f"/api/menu/items/{self.item_b.id}/",
			{"name": "Updated B dish"},
			format="json",
		)

		self.assertEqual(own_update.status_code, status.HTTP_200_OK)
		self.assertEqual(other_update.status_code, status.HTTP_404_NOT_FOUND)

	def test_customer_qr_table_order_creation_remains_available(self):
		self.client.force_authenticate(self.customer)
		restaurants_response = self.client.get("/api/restaurants/restaurants/")
		tables_response = self.client.get("/api/restaurants/tables/")
		categories_response = self.client.get("/api/menu/categories/")
		items_response = self.client.get("/api/menu/items/")

		self.assertEqual(restaurants_response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in restaurants_response.data}, {self.restaurant_a.id, self.restaurant_b.id})
		self.assertEqual(tables_response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in tables_response.data}, {self.table_a.id, self.table_b.id})
		self.assertEqual(categories_response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in categories_response.data}, {self.category_a.id, self.category_b.id})
		self.assertEqual(items_response.status_code, status.HTTP_200_OK)
		self.assertEqual({row["id"] for row in items_response.data}, {self.item_a.id, self.item_b.id})

		response = self.client.post(
			"/api/orders/orders/",
			{
				"restaurant": self.restaurant_a.id,
				"table": self.table_a.id,
				"customer_name": "QR guest",
				"items": [{"menu_item": self.item_a.id, "quantity": 1}],
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["table"], self.table_a.id)
		self.assertEqual(float(response.data["total_amount"]), 12.0)

	def test_owner_can_add_existing_staff_to_another_restaurant(self):
		self.client.force_authenticate(self.owner_b)

		response = self.client.post(
			self.staff_url,
			{
				"restaurant": self.restaurant_b.id,
				"username": self.manager.username,
				"role": User.Role.WAITER,
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["username"], self.manager.username)
		self.assertEqual(response.data["role"], User.Role.WAITER)
		self.assertTrue(
			RestaurantStaff.objects.filter(
				user=self.manager,
				restaurant=self.restaurant_a,
			).exists()
		)
