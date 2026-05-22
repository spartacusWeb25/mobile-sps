from Pisos.models import StatusPisos


class StatusPisosService:

    @staticmethod
    def mapa_status(banco, empresa, filial, tipo):
        status = StatusPisos.objects.using(banco).filter(
            stat_empr=empresa,
            stat_fili=filial,
            stat_tipo=tipo,
            stat_ativo=True,
        )

        return {
            s.stat_codigo: s
            for s in status
        }