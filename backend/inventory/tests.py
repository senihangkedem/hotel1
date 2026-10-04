from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from menu.models import Category, MenuItem, MenuItemIngredient
from orders.models import Order
from restaurants.models import Restaurant, RestaurantStaff, RestaurantTable

from .models import InventoryItem, InventoryTransaction
from .services import transition_order_status


User = get_user_model()


class RecipeManagementTests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user("recipe-owner", password="test-password", role="OWNER")
		self.other_owner = User.objects.create_user("recipe-other", password="test-password", role="OWNER")
		self.customer = User.objects.create_user("recipe-customer", password="test-password", role="CUSTOMER")
		self.kitchen = User.objects.create_user("recipe-kitchen", password="test-password", role="KITCHEN")
		self.manager = User.objects.create_user("recipe-manager", password="test-password", role="MANAGER")
		self.superuser = User.objects.create_superuser("recipe-admin", password="test-password")
		self.restaurant = Restaurant.objects.create(owner=self.owner, name="Recipe House", address="1 Recipe Road")
		self.other_restaurant = Restaurant.objects.create(owner=self.other_owner, name="Other House", address="2 Recipe Road")
		self.category = Category.objects.create(restaurant=self.restaurant, name="Mains")
		self.menu_item = MenuItem.objects.create(
			restaurant=self.restaurant,
			category=self.category,
			name="Chicken Momo",
			price="10.00",
		)
		self.other_menu_item = MenuItem.objects.create(
			restaurant=self.other_restaurant,
			name="Other Dish",
			price="12.00",
		)
		self.chicken = InventoryItem.objects.create(
			restaurant=self.restaurant,
			name="Chicken",
			unit=InventoryItem.Unit.KILOGRAM,
			quantity_on_hand="5.000",
		)
		self.other_stock = InventoryItem.objects.create(
			restaurant=self.other_restaurant,
			name="Other Chicken",
			unit=InventoryItem.Unit.KILOGRAM,
			quantity_on_hand="5.000",
		)
		self.url = "/api/menu/recipes/"

	def recipe_payload(self, **overrides):
		payload = {
			"menu_item": self.menu_item.id,
			"inventory_item": self.chicken.id,
			"quantity_required": "0.050",
			"unit": "kg",
		}
		payload.update(overrides)
		return payload

	def test_owner_can_create_update_and_remove_recipe(self):
		self.client.force_authenticate(self.owner)
		created = self.client.post(self.url, self.recipe_payload(), format="json")
		self.assertEqual(created.status_code, status.HTTP_201_CREATED)
		recipe_id = created.data["id"]

		updated = self.client.patch(
			f"{self.url}{recipe_id}/",
			{"quantity_required": "0.075"},
			format="json",
		)
		deleted = self.client.delete(f"{self.url}{recipe_id}/")

		self.assertEqual(updated.status_code, status.HTTP_200_OK)
		self.assertEqual(Decimal(updated.data["quantity_required"]), Decimal("0.075"))
		self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

	def test_unauthorized_customer_cannot_access_recipe_management(self):
		self.client.force_authenticate(self.customer)

		list_response = self.client.get(self.url)
		create_response = self.client.post(self.url, self.recipe_payload(), format="json")

		self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_kitchen_can_read_recipe_but_cannot_edit_it(self):
		recipe = MenuItemIngredient.objects.create(
			menu_item=self.menu_item,
			inventory_item=self.chicken,
			quantity_required="0.050",
			unit="kg",
		)
		RestaurantStaff.objects.create(
			user=self.kitchen,
			restaurant=self.restaurant,
			role=User.Role.KITCHEN,
		)
		self.client.force_authenticate(self.kitchen)

		list_response = self.client.get(self.url)
		update_response = self.client.patch(
			f"{self.url}{recipe.id}/",
			{"quantity_required": "0.060"},
			format="json",
		)

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(list_response.data), 1)
		self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_active_manager_can_create_recipe(self):
		RestaurantStaff.objects.create(
			user=self.manager,
			restaurant=self.restaurant,
			role=User.Role.MANAGER,
		)
		self.client.force_authenticate(self.manager)

		response = self.client.post(self.url, self.recipe_payload(), format="json")

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)

	def test_recipe_rejects_cross_restaurant_and_incompatible_units(self):
		self.client.force_authenticate(self.owner)

		cross_restaurant = self.client.post(
			self.url,
			self.recipe_payload(inventory_item=self.other_stock.id),
			format="json",
		)
		incompatible = self.client.post(
			self.url,
			self.recipe_payload(unit="litre"),
			format="json",
		)

		self.assertEqual(cross_restaurant.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(incompatible.status_code, status.HTTP_400_BAD_REQUEST)

	def test_recipe_rejects_zero_and_negative_quantities(self):
		self.client.force_authenticate(self.owner)

		zero = self.client.post(self.url, self.recipe_payload(quantity_required="0"), format="json")
		negative = self.client.post(self.url, self.recipe_payload(quantity_required="-1"), format="json")

		self.assertEqual(zero.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(negative.status_code, status.HTTP_400_BAD_REQUEST)

	def test_compatible_gram_recipe_converts_to_kilogram_stock(self):
		self.client.force_authenticate(self.owner)

		response = self.client.post(
			self.url,
			self.recipe_payload(quantity_required="50", unit="g"),
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)

	def test_superuser_can_manage_recipe_even_with_customer_app_role(self):
		self.client.force_authenticate(self.superuser)

		response = self.client.post(self.url, self.recipe_payload(), format="json")

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class OrderInventoryTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user("inventory-owner", password="test-password", role="OWNER")
		self.customer = User.objects.create_user("inventory-customer", password="test-password", role="CUSTOMER")
		self.restaurant = Restaurant.objects.create(owner=self.owner, name="Stock House", address="3 Stock Road")
		self.table = RestaurantTable.objects.create(restaurant=self.restaurant, table_number=1)
		self.menu_item = MenuItem.objects.create(
			restaurant=self.restaurant,
			name="Momo",
			price="10.00",
		)
		self.chicken = InventoryItem.objects.create(
			restaurant=self.restaurant,
			name="Chicken",
			unit=InventoryItem.Unit.KILOGRAM,
			quantity_on_hand="5.000",
		)
		self.flour = InventoryItem.objects.create(
			restaurant=self.restaurant,
			name="Flour",
			unit=InventoryItem.Unit.GRAM,
			quantity_on_hand="5000.000",
		)
		MenuItemIngredient.objects.create(
			menu_item=self.menu_item,
			inventory_item=self.chicken,
			quantity_required="0.050",
			unit="kg",
		)
		MenuItemIngredient.objects.create(
			menu_item=self.menu_item,
			inventory_item=self.flour,
			quantity_required="80.000",
			unit="g",
		)

	def create_order(self, quantity=10, status_value=Order.Status.CONFIRMED):
		return Order.objects.create(
			restaurant=self.restaurant,
			table=self.table,
			customer=self.customer,
			status=status_value,
			total_amount=Decimal("10.00") * quantity,
		), quantity

	def create_order_line(self, order, quantity):
		from orders.models import OrderItem

		OrderItem.objects.create(
			order=order,
			menu_item=self.menu_item,
			quantity=quantity,
			unit_price="10.00",
			subtotal=Decimal("10.00") * quantity,
		)

	def test_confirmed_to_preparing_deducts_multiple_ingredients_and_quantities(self):
		order, quantity = self.create_order(10)
		self.create_order_line(order, quantity)

		updated = transition_order_status(order.id, Order.Status.PREPARING, self.owner)

		self.chicken.refresh_from_db()
		self.flour.refresh_from_db()
		self.assertEqual(updated.status, Order.Status.PREPARING)
		self.assertEqual(updated.total_amount, Decimal("100.00"))
		self.assertEqual(self.chicken.quantity_on_hand, Decimal("4.500"))
		self.assertEqual(self.flour.quantity_on_hand, Decimal("4200.000"))
		self.assertEqual(
			InventoryTransaction.objects.filter(order=order, transaction_type=InventoryTransaction.Type.OUT).count(),
			2,
		)

	def test_insufficient_stock_rolls_back_status_and_all_stock(self):
		self.chicken.quantity_on_hand = Decimal("0.200")
		self.chicken.save(update_fields=["quantity_on_hand"])
		order, quantity = self.create_order(10)
		self.create_order_line(order, quantity)

		with self.assertRaises(ValidationError):
			transition_order_status(order.id, Order.Status.PREPARING, self.owner)

		order.refresh_from_db()
		self.chicken.refresh_from_db()
		self.flour.refresh_from_db()
		self.assertEqual(order.status, Order.Status.CONFIRMED)
		self.assertEqual(self.chicken.quantity_on_hand, Decimal("0.200"))
		self.assertEqual(self.flour.quantity_on_hand, Decimal("5000.000"))
		self.assertFalse(InventoryTransaction.objects.filter(order=order).exists())

	def test_repeated_status_request_does_not_deduct_twice_and_orders_are_independent(self):
		first, first_quantity = self.create_order(2)
		second, second_quantity = self.create_order(3)
		self.create_order_line(first, first_quantity)
		self.create_order_line(second, second_quantity)

		transition_order_status(first.id, Order.Status.PREPARING, self.owner)
		transition_order_status(first.id, Order.Status.PREPARING, self.owner)
		transition_order_status(second.id, Order.Status.PREPARING, self.owner)

		self.chicken.refresh_from_db()
		self.assertEqual(self.chicken.quantity_on_hand, Decimal("4.750"))
		self.assertEqual(
			InventoryTransaction.objects.filter(
				order=first,
				transaction_type=InventoryTransaction.Type.OUT,
			).count(),
			2,
		)

	def test_deduction_rolls_back_when_ledger_write_fails(self):
		order, quantity = self.create_order(1)
		self.create_order_line(order, quantity)

		with patch("inventory.services.InventoryTransaction.objects.create", side_effect=RuntimeError("ledger unavailable")):
			with self.assertRaises(RuntimeError):
				transition_order_status(order.id, Order.Status.PREPARING, self.owner)

		order.refresh_from_db()
		self.chicken.refresh_from_db()
		self.assertEqual(order.status, Order.Status.CONFIRMED)
		self.assertEqual(self.chicken.quantity_on_hand, Decimal("5.000"))
		self.assertFalse(InventoryTransaction.objects.filter(order=order).exists())

	def test_cancel_after_preparing_creates_idempotent_reversal_without_mutating_out(self):
		order, quantity = self.create_order(2)
		self.create_order_line(order, quantity)
		transition_order_status(order.id, Order.Status.PREPARING, self.owner)
		outgoing = InventoryTransaction.objects.get(
			order=order,
			inventory_item=self.chicken,
			transaction_type=InventoryTransaction.Type.OUT,
		)

		transition_order_status(order.id, Order.Status.CANCELLED, self.owner)
		transition_order_status(order.id, Order.Status.CANCELLED, self.owner)

		self.chicken.refresh_from_db()
		outgoing.refresh_from_db()
		reversal = InventoryTransaction.objects.get(
			order=order,
			inventory_item=self.chicken,
			transaction_type=InventoryTransaction.Type.REVERSAL,
		)
		self.assertEqual(self.chicken.quantity_on_hand, Decimal("5.000"))
		self.assertEqual(outgoing.quantity, Decimal("0.100"))
		self.assertEqual(reversal.quantity, Decimal("0.100"))
		self.assertEqual(InventoryTransaction.objects.filter(order=order).count(), 4)

	def test_manual_in_out_and_adjustment_are_recorded_and_cannot_make_stock_negative(self):
		from .services import create_manual_transaction

		create_manual_transaction(
			inventory_item_id=self.chicken.id,
			transaction_type=InventoryTransaction.Type.IN,
			quantity=Decimal("1.000"),
			user=self.owner,
		)
		create_manual_transaction(
			inventory_item_id=self.chicken.id,
			transaction_type=InventoryTransaction.Type.OUT,
			quantity=Decimal("0.500"),
			user=self.owner,
		)
		create_manual_transaction(
			inventory_item_id=self.chicken.id,
			transaction_type=InventoryTransaction.Type.ADJUSTMENT,
			quantity=Decimal("-0.250"),
			user=self.owner,
		)

		self.chicken.refresh_from_db()
		self.assertEqual(self.chicken.quantity_on_hand, Decimal("5.250"))
		self.assertEqual(
			InventoryTransaction.objects.filter(
				inventory_item=self.chicken,
				source=InventoryTransaction.Source.MANUAL,
			).count(),
			3,
		)
		with self.assertRaises(ValidationError):
			create_manual_transaction(
				inventory_item_id=self.chicken.id,
				transaction_type=InventoryTransaction.Type.OUT,
				quantity=Decimal("99.000"),
				user=self.owner,
			)


class OrderTransitionAPITests(APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user("transition-owner", password="test-password", role="OWNER")
		self.manager = User.objects.create_user("transition-manager", password="test-password", role="MANAGER")
		self.customer = User.objects.create_user("transition-customer", password="test-password", role="CUSTOMER")
		self.restaurant = Restaurant.objects.create(
			owner=self.owner,
			name="Transition House",
			address="4 Transition Road",
		)
		RestaurantStaff.objects.create(
			user=self.manager,
			restaurant=self.restaurant,
			role=User.Role.MANAGER,
		)
		self.menu_item = MenuItem.objects.create(
			restaurant=self.restaurant,
			name="Transition Momo",
			price="8.00",
		)
		self.stock = InventoryItem.objects.create(
			restaurant=self.restaurant,
			name="Transition Chicken",
			unit=InventoryItem.Unit.KILOGRAM,
			quantity_on_hand="2.000000",
		)
		MenuItemIngredient.objects.create(
			menu_item=self.menu_item,
			inventory_item=self.stock,
			quantity_required="0.050000",
			unit="kg",
		)
		self.order = Order.objects.create(
			restaurant=self.restaurant,
			customer=self.customer,
			status=Order.Status.CONFIRMED,
			total_amount="16.00",
		)
		from orders.models import OrderItem

		OrderItem.objects.create(
			order=self.order,
			menu_item=self.menu_item,
			quantity=2,
			unit_price="8.00",
			subtotal="16.00",
		)
		self.url = f"/api/orders/orders/{self.order.id}/transition/"

	def test_manager_transition_deducts_once_and_repeated_request_is_idempotent(self):
		self.client.force_authenticate(self.manager)

		first = self.client.post(self.url, {"status": Order.Status.PREPARING}, format="json")
		repeated = self.client.post(self.url, {"status": Order.Status.PREPARING}, format="json")

		self.stock.refresh_from_db()
		self.assertEqual(first.status_code, status.HTTP_200_OK)
		self.assertEqual(repeated.status_code, status.HTTP_200_OK)
		self.assertEqual(self.stock.quantity_on_hand, Decimal("1.900000"))
		self.assertEqual(
			InventoryTransaction.objects.filter(order=self.order, transaction_type=InventoryTransaction.Type.OUT).count(),
			1,
		)

	def test_customer_cannot_trigger_deduction(self):
		self.client.force_authenticate(self.customer)

		response = self.client.post(self.url, {"status": Order.Status.PREPARING}, format="json")

		self.order.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(self.order.status, Order.Status.CONFIRMED)
		self.assertEqual(self.stock.quantity_on_hand, Decimal("2.000000"))

	def test_insufficient_stock_keeps_order_confirmed(self):
		self.stock.quantity_on_hand = Decimal("0.050000")
		self.stock.save(update_fields=["quantity_on_hand"])
		self.client.force_authenticate(self.manager)

		response = self.client.post(self.url, {"status": Order.Status.PREPARING}, format="json")

		self.order.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(self.order.status, Order.Status.CONFIRMED)
		self.assertEqual(self.stock.quantity_on_hand, Decimal("0.050000"))

	def test_customer_cannot_cancel_or_reverse_deducted_order(self):
		self.client.force_authenticate(self.manager)
		preparing = self.client.post(self.url, {"status": Order.Status.PREPARING}, format="json")
		self.assertEqual(preparing.status_code, status.HTTP_200_OK)

		self.client.force_authenticate(self.customer)
		cancellation = self.client.post(self.url, {"status": Order.Status.CANCELLED}, format="json")

		self.order.refresh_from_db()
		self.stock.refresh_from_db()
		self.assertEqual(cancellation.status_code, status.HTTP_403_FORBIDDEN)
		self.assertEqual(self.order.status, Order.Status.PREPARING)
		self.assertEqual(self.stock.quantity_on_hand, Decimal("1.900000"))
		self.assertFalse(
			InventoryTransaction.objects.filter(
				order=self.order,
				transaction_type=InventoryTransaction.Type.REVERSAL,
			).exists()
		)
