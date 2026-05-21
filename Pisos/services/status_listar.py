from Pisos.models import StatusPisos


class StatusListar:
    @staticmethod
    def status_orcamentos_listar(self, banco, empr, fili,):
        return StatusPisos.objects.using(banco).filter(stat_empr=empr, stat_fili=fili, stat_tipo=0).order_by('-stat_id')
    
    @staticmethod
    def status_pedidos_listar(self, banco, empr, fili,):
        return StatusPisos.objects.using(banco).filter(stat_empr=empr, stat_fili=fili, stat_tipo=1).order_by('-stat_id')
