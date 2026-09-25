from ..models import OcorrenciaTransp, PerfilOcorrencia

class OcorrenciaService:
    @staticmethod
    def criar_ocorrencia(*, banco, empresa, filial, codigo, descricao="", finalizadora=False):
        return OcorrenciaTransp.objects.using(banco).create(
            ocor_empr = empresa,
            ocor_fili = filial,
            ocor_codi = codigo,
            ocor_desc = descricao,
            ocor_fina = finalizadora,
        )

    @staticmethod
    def criar_perfil(*, banco, empresa, filial, descricao="", ativo=True, ocorrencias=[]):
        unique_ocorrencias = list(set(filter(None, ocorrencias)))

        perfil = PerfilOcorrencia.objects.using(banco).create(
            pfoc_empr = empresa,
            pfoc_fili = filial,
            pfoc_desc = descricao,
            pfoc_ativ = ativo,
        )
        if unique_ocorrencias:
            perfil.ocorrencias.add(*unique_ocorrencias)

        return perfil

    @staticmethod
    def atualizar_perfil(*, banco, empresa, filial, id, descricao="", ocorrencias=None):
        if ocorrencias is None:
            ocorrencias = []

        try:
            perfil = PerfilOcorrencia.objects.using(banco).prefetch_related("ocorrencias").get(
                pfoc_empr = empresa,
                pfoc_fili = filial,
                id = id,
            )
        except PerfilOcorrencia.DoesNotExist:
            return None
        perfil.pfoc_desc = descricao
        perfil.save(using=banco)
        unique_ocorrencias = list(set(filter(None, ocorrencias)))
        perfil.ocorrencias.set(unique_ocorrencias)

        return perfil

    def perfil_toggle_ativar(*, banco, empresa, filial, id):
        try:
            perfil = PerfilOcorrencia.objects.using(banco).prefetch_related("ocorrencias").get(
                pfoc_empr = empresa,
                pfoc_fili = filial,
                id = id,
            )
        except PerfilOcorrencia.DoesNotExist:
            return None
        perfil.pfoc_ativ = not perfil.pfoc_ativ
        perfil.save(using=banco)
        return perfil