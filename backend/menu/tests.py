from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from restaurants.models import Restaurant

from .models import Category, MenuItem


User = get_user_model()


class MenuSecurityTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			username="menu-owner",
			password="test-password",
			role="OWNER",
		)
		self.other_owner = User.objects.create_user(
			username="menu-other-owner",
			password="test-password",
			role="OWNER",
		)
		self.customer = User.objects.create_user(
			username="menu-customer",
			password="test-password",
			role="CUSTOMER",
		)
		self.superuser = User.objects.create_superuser(
			username="menu-superuser",
			password="test-password",
		)
		self.restaurant = Restaurant.objects.create(
			owner=self.owner,
			name="Menu Owner Restaurant",
			address="1 Menu Street",
		)
		self.other_restaurant = Restaurant.objects.create(
			owner=self.other_owner,
			name="Menu Other Restaurant",
			address="2 Menu Street",
		)
		self.category = Category.objects.create(
			restaurant=self.restaurant,
			name="Main Course",
		)
		self.other_category = Category.objects.create(
			restaurant=self.other_restaurant,
			name="Other Course",
		)
		self.menu_item = MenuItem.objects.create(
			restaurant=self.other_restaurant,
			category=self.other_category,
			name="Other Item",
			price="10.00",
		)
		self.category_url = "/api/menu/categories/"
		self.item_url = "/api/menu/items/"

	def category_payload(self, restaurant=None):
		return {
			"restaurant": (restaurant or self.restaurant).id,
			"name": "Desserts",
			"description": "Sweet dishes",
			"is_active": True,
		}

	def item_payload(self, restaurant=None, category=None, price="12.50"):
		return {
			"restaurant": (restaurant or self.restaurant).id,
			"category": (category or self.category).id,
			"name": "Valid Item",
			"description": "A valid menu item",
			"price": price,
			"is_available": True,
			"is_featured": False,
		}

	def test_owner_can_create_category_for_their_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(
			self.category_url,
			self.category_payload(),
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["restaurant"], self.restaurant.id)

	def test_owner_cannot_create_category_for_another_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(
			self.category_url,
			self.category_payload(self.other_restaurant),
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_owner_cannot_access_or_modify_another_owners_category(self):
		self.client.force_authenticate(self.owner)
		detail_url = f"{self.category_url}{self.other_category.id}/"

		list_response = self.client.get(self.category_url)
		update_response = self.client.patch(detail_url, {"name": "Changed"})
		delete_response = self.client.delete(detail_url)

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{item["id"] for item in list_response.data},
			{self.category.id},
		)
		self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

	def test_customer_can_read_categories_but_cannot_manage_them(self):
		self.client.force_authenticate(self.customer)

		create_response = self.client.post(
			self.category_url,
			self.category_payload(),
		)
		list_response = self.client.get(self.category_url)

		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{item["id"] for item in list_response.data},
			{self.category.id, self.other_category.id},
		)

	def test_superuser_can_access_all_categories(self):
		self.client.force_authenticate(self.superuser)

		response = self.client.get(self.category_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 2)

	def test_owner_can_create_menu_item_for_their_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(
			self.item_url,
			self.item_payload(),
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data["restaurant"], self.restaurant.id)

	def test_owner_cannot_create_menu_item_for_another_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(
			self.item_url,
			self.item_payload(self.other_restaurant, self.other_category),
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_owner_cannot_access_or_modify_another_owners_menu_item(self):
		self.client.force_authenticate(self.owner)
		detail_url = f"{self.item_url}{self.menu_item.id}/"

		list_response = self.client.get(self.item_url)
		update_response = self.client.patch(detail_url, {"name": "Changed"})
		delete_response = self.client.delete(detail_url)

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{item["id"] for item in list_response.data},
			set(),
		)
		self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)

	def test_customer_can_read_menu_items_but_cannot_manage_them(self):
		self.client.force_authenticate(self.customer)

		create_response = self.client.post(
			self.item_url,
			self.item_payload(),
		)
		list_response = self.client.get(self.item_url)

		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(
			{item["id"] for item in list_response.data},
			{self.menu_item.id},
		)

	def test_superuser_can_access_all_menu_items(self):
		self.client.force_authenticate(self.superuser)

		response = self.client.get(self.item_url)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(response.data), 1)

	def test_menu_item_category_must_belong_to_selected_restaurant(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(
			self.item_url,
			self.item_payload(self.restaurant, self.other_category),
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("category", response.data)

	def test_menu_item_accepts_same_restaurant_category_or_no_category(self):
		self.client.force_authenticate(self.owner)

		valid_response = self.client.post(
			self.item_url,
			self.item_payload(),
		)
		no_category_payload = self.item_payload()
		no_category_payload.pop("category")
		no_category_response = self.client.post(
			self.item_url,
			no_category_payload,
		)

		self.assertEqual(valid_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(no_category_response.status_code, status.HTTP_201_CREATED)

	def test_menu_item_rejects_negative_price_and_blank_name(self):
		self.client.force_authenticate(self.owner)

		negative_price = self.item_payload(price="-1.00")
		blank_name = self.item_payload()
		blank_name["name"] = "   "

		negative_response = self.client.post(self.item_url, negative_price)
		blank_response = self.client.post(self.item_url, blank_name)

		self.assertEqual(negative_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(blank_response.status_code, status.HTTP_400_BAD_REQUEST)
