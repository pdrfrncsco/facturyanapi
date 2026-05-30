from decimal import Decimal, ROUND_HALF_UP

MONEY_PLACES = Decimal("0.01")
QTY_PLACES = Decimal("0.001")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QTY_PLACES, rounding=ROUND_HALF_UP)
