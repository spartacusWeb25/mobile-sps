from django import template
from decimal import Decimal

register = template.Library()


def _format_brl(value: Decimal) -> str:
    # Formata com separador de milhar americano e converte para padrão BR
    s = f"{value:,.2f}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {s}"


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(value)
    except Exception:
        return Decimal(str(value).replace(",", "."))


def _format_numbr(value: Decimal, places: int) -> str:
    s = f"{value:,.{places}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter(name="brl")
def brl(value) -> str:
    """Formata números para moeda BRL sem depender de locale do SO.
    Exemplos: 1234.5 -> R$ 1.234,50; None/invalid -> R$ 0,00
    """
    if value is None:
        return "R$ 0,00"
    try:
        val = _to_decimal(value)
    except Exception:
        return "R$ 0,00"
    return _format_brl(val)


@register.filter(name="numbr")
def numbr(value, places="2") -> str:
    try:
        val = _to_decimal(value)
    except Exception:
        return "0,00"

    p = str(places or "2").strip().lower()
    if p == "auto":
        s = _format_numbr(val, 2)
        if "," in s:
            s = s.rstrip("0").rstrip(",")
        return s

    try:
        n = int(p)
    except Exception:
        n = 2
    return _format_numbr(val, n)

