# Pisos/services/status_pisos_seed_service.py

from Pisos.models import StatusPisos


STATUS_ORCAMENTO = [
    {"codigo": 0, "desc": "ABERTO"},
    {"codigo": 1, "desc": "CANCELADO"},
    {"codigo": 2, "desc": "EXPORTADO PEDIDO"},
]

STATUS_PEDIDO = [
    {"codigo": 0, "desc": "Aguardando Financeiro"},
    {"codigo": 1, "desc": "Aguardando Compras"},
    {"codigo": 2, "desc": "Compra Efetuada"},
    {"codigo": 3, "desc": "Material Disponível"},
    {"codigo": 4, "desc": "Logística"},
    {"codigo": 5, "desc": "Cancelado"},
    {"codigo": 6, "desc": "Concluído"},
]


class StatusPisosSeedService:

    @staticmethod
    def criar_padrao(banco, empr, fili):
        registros = []

        for item in STATUS_ORCAMENTO:
            registros.append(StatusPisos(
                stat_empr=empr,
                stat_fili=fili,
                stat_tipo=StatusPisos.TIPO_ORCAMENTO,
                stat_codigo=item["codigo"],
                stat_desc=item["desc"],
            ))

        for item in STATUS_PEDIDO:
            registros.append(StatusPisos(
                stat_empr=empr,
                stat_fili=fili,
                stat_tipo=StatusPisos.TIPO_PEDIDO,
                stat_codigo=item["codigo"],
                stat_desc=item["desc"],
            ))

        return StatusPisos.objects.using(banco).bulk_create(
            registros,
            ignore_conflicts=True
        )