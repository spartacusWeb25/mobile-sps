from ..models import PedidoOcorrencia

class OcorrenciaService:
    @staticmethod
    def create_ocorrencia(*, banco, empresa, filial, codigo, descricao="", finalizadora=False):
        return PedidoOcorrencia.objects.using(banco).create(
            ocor_empr = empresa,
            ocor_fili = filial,
            ocor_codi = codigo,
            ocor_desc = descricao,
            ocor_fina = finalizadora,
        )