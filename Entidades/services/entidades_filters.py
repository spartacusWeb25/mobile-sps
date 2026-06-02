from django.db.models import Q


def apply_vinculo_filters(queryset, has_vendedor=None, has_arquiteto=None):
    """Aplica filtros de vínculo com vendedor e arquiteto.

    has_vendedor / has_arquiteto: valores verdadeiros são '1', True, 'true'.
    Filtragem adotada: considera vinculado quando o campo é maior que zero.
    """
    def _is_true(val):
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        try:
            return str(val).strip().lower() in {'1', 'true', 'sim', 'yes', 'on'}
        except Exception:
            return False

    if _is_true(has_vendedor):
        # considera vinculado quando enti_vend > 0
        queryset = queryset.filter(enti_vend__isnull=False).exclude(enti_vend=0)

    if _is_true(has_arquiteto):
        # considera vinculado quando enti_arqu > 0
        queryset = queryset.filter(enti_arqu__isnull=False).exclude(enti_arqu=0)

    return queryset
