from Pisos.models import StatusPisos


class StatusCriar:
    @staticmethod
    def status_orcamentos_criar(banco, empr, fili):
        qs = StatusPisos.objects.using(banco).filter(stat_empr=empr, stat_fili=fili)
        last = qs.order_by("-stat_codigo").first()
        ultimo_cod = last.stat_codigo + 1 if last else 1
        obj = StatusPisos(stat_empr=empr, stat_fili=fili, stat_codigo=ultimo_cod, stat_desc="Orçamento", stat_tipo=0)
        obj.save(using=banco)
        return obj
    
    @staticmethod
    def status_pedidos_criar(banco, empr, fili):
        qs = StatusPisos.objects.using(banco).filter(stat_empr=empr, stat_fili=fili)
        last = qs.order_by("-stat_codigo").first()
        ultimo_cod = last.stat_codigo + 1 if last else 1
        obj = StatusPisos(stat_empr=empr, stat_fili=fili, stat_codigo=ultimo_cod, stat_desc="Pedido", stat_tipo=1)
        obj.save(using=banco)
        return obj
