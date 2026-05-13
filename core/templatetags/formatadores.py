from django import template
from decimal import Decimal, InvalidOperation
from datetime import date, datetime

register = template.Library()


@register.filter(name="data_br")
def data_br(value):
    if not value:
        return ""

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")

    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(value)


@register.filter(name="brl")
def brl(value):
    if value is None or value == "":
        value = 0

    try:
        valor = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        valor = Decimal("0")

    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")

    return f"R$ {texto}"


@register.filter(name="qtd_br")
def qtd_br(value):
    if value is None or value == "":
        value = 0

    try:
        valor = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        valor = Decimal("0")

    texto = f"{valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")