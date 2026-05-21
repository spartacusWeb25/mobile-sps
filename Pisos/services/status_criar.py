from Pisos.models import StatusPisos


class StatusListar:
    @staticmethod
    def status_orcamentos_criar(self, banco, empr, fili):
        return StatusPisos.objects.create(stat_empr=empr, stat_fili=fili, stat_tipo=0).save(using=banco)
    
    @staticmethod
    def status_pedidos_criar(self, banco, empr, fili):
        return StatusPisos.objects.create(stat_empr=empr, stat_fili=fili, stat_tipo=1).save(using=banco)
