from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from user_accounts.models import User


class Restaurant(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="restaurants",
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    address = models.CharField(max_length=255)

    logo = models.ImageField(
        upload_to="restaurant_logos/",
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(default=True)

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    service_charge_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(tax_rate__gte=0, tax_rate__lte=100), name="restaurant_tax_rate_range"),
            models.CheckConstraint(condition=models.Q(service_charge_rate__gte=0, service_charge_rate__lte=100), name="restaurant_service_charge_rate_range"),
        ]

    def __str__(self):
        return self.name


class RestaurantTable(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="tables",
    )

    table_number = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField(default=4)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("restaurant", "table_number")
        ordering = ["table_number"]

    def __str__(self):
        return f"{self.restaurant.name} - Table {self.table_number}"


class RestaurantStaff(models.Model):
    STAFF_ROLE_CHOICES = tuple(
        (role, label)
        for role, label in User.Role.choices
        if role not in {User.Role.OWNER, User.Role.CUSTOMER}
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="restaurant_memberships",
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="staff_memberships",
    )
    role = models.CharField(max_length=20, choices=STAFF_ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "restaurant"],
                name="unique_restaurant_staff_membership",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.restaurant.name} ({self.role})"