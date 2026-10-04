from django.db import models
from restaurants.models import Restaurant
from inventory.models import InventoryItem


class Category(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="categories",
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="menu_items",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    image = models.ImageField(
        upload_to="menu_items/",
        blank=True,
        null=True,
    )

    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class MenuItemIngredient(models.Model):
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name="recipe_ingredients",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="menu_recipes",
    )
    quantity_required = models.DecimalField(max_digits=15, decimal_places=6)
    unit = models.CharField(max_length=10, choices=InventoryItem.Unit.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["inventory_item__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["menu_item", "inventory_item"],
                name="unique_recipe_ingredient_per_menu_item",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_required__gt=0),
                name="recipe_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.menu_item.name}: {self.quantity_required} {self.unit} {self.inventory_item.name}"