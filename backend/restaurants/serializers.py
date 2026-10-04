from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Restaurant, RestaurantStaff, RestaurantTable
from .permissions import can_manage_restaurant


User = get_user_model()


class RestaurantTableSerializer(serializers.ModelSerializer):
    table_number = serializers.IntegerField(min_value=1)
    capacity = serializers.IntegerField(min_value=1)

    class Meta:
        model = RestaurantTable
        fields = [
            "id",
            "restaurant",
            "table_number",
            "capacity",
            "is_active",
        ]

    def validate(self, attrs):
        restaurant = attrs.get(
            "restaurant",
            self.instance.restaurant if self.instance else None,
        )
        user = self.context["request"].user

        if restaurant is None:
            raise serializers.ValidationError({
                "restaurant": "A restaurant is required.",
            })

        if not can_manage_restaurant(user, restaurant.id):
            raise serializers.ValidationError({
                "restaurant": "You can only manage tables in restaurants you own or manage.",
            })

        return attrs


class RestaurantStaffSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True)
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)

    class Meta:
        model = RestaurantStaff
        fields = [
            "id",
            "restaurant",
            "restaurant_name",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "restaurant",
            "restaurant_name",
            "username",
            "first_name",
            "last_name",
            "email",
            "created_at",
            "updated_at",
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if "phone" in user_data:
            instance.user.phone = user_data["phone"]
            instance.user.save(update_fields=["phone"])

        for field in ("role", "is_active"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        instance.save()
        return instance


class RestaurantStaffCreateSerializer(serializers.Serializer):
    restaurant = serializers.PrimaryKeyRelatedField(queryset=Restaurant.objects.all())
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=RestaurantStaff.STAFF_ROLE_CHOICES)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["request"].user
        restaurant = attrs["restaurant"]
        if not user.is_superuser and restaurant.owner_id != user.id:
            raise serializers.ValidationError({
                "restaurant": "You can only add staff to restaurants you own.",
            })

        existing_user = User.objects.filter(username=attrs["username"]).first()
        if existing_user:
            if existing_user.role in (User.Role.OWNER, User.Role.CUSTOMER) or not existing_user.is_active:
                raise serializers.ValidationError({
                    "username": "This account cannot be added as restaurant staff.",
                })
            if "password" in attrs:
                raise serializers.ValidationError({
                    "password": "An existing staff account's password cannot be changed here.",
                })
            if RestaurantStaff.objects.filter(user=existing_user, restaurant=restaurant).exists():
                raise serializers.ValidationError({
                    "username": "This user is already assigned to this restaurant.",
                })
            attrs["existing_user"] = existing_user
        else:
            password = attrs.get("password")
            if not password:
                raise serializers.ValidationError({"password": "A password is required for a new staff account."})
            password_user = User(username=attrs["username"], email=attrs.get("email", ""))
            validate_password(password, user=password_user)

        return attrs

    def create(self, validated_data):
        existing_user = validated_data.pop("existing_user", None)
        restaurant = validated_data.pop("restaurant")
        role = validated_data.pop("role")
        password = validated_data.pop("password", None)
        username = validated_data.pop("username")

        if existing_user:
            staff_user = existing_user
        else:
            staff_user = User.objects.create_user(
                username=username,
                first_name=validated_data.get("first_name", ""),
                last_name=validated_data.get("last_name", ""),
                email=validated_data.get("email", ""),
                password=password,
                phone=validated_data.get("phone", ""),
                role=role,
            )

        return RestaurantStaff.objects.create(
            user=staff_user,
            restaurant=restaurant,
            role=role,
        )

    def to_representation(self, instance):
        return RestaurantStaffSerializer(instance, context=self.context).data


class RestaurantSerializer(serializers.ModelSerializer):
    tables = RestaurantTableSerializer(many=True, read_only=True)

    class Meta:
        model = Restaurant
        fields = [
            "id",
            "owner",
            "name",
            "description",
            "phone",
            "email",
            "address",
            "logo",
            "is_active",
            "created_at",
            "updated_at",
            "tables",
        ]
        read_only_fields = ["owner"]