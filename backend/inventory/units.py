from decimal import Decimal

from rest_framework.exceptions import ValidationError


UNIT_FACTORS = {
    "kg": ("mass", Decimal("1000")),
    "g": ("mass", Decimal("1")),
    "litre": ("volume", Decimal("1000")),
    "ml": ("volume", Decimal("1")),
    "piece": ("count", Decimal("1")),
}


def convert_quantity(quantity, source_unit, target_unit):
    source_dimension, source_factor = UNIT_FACTORS[source_unit]
    target_dimension, target_factor = UNIT_FACTORS[target_unit]
    if source_dimension != target_dimension:
        raise ValidationError({"unit": "Recipe unit is incompatible with the inventory item unit."})
    return quantity * source_factor / target_factor