from django.db import transaction
from django.db.models import Max

from Licencas.models import Empresas
from controledevisitas.models import Etapavisita


class EtapaOrcamentoGeradoService:
    def __init__(self, *, banco: str, empresa_id: int):
        self.banco = banco
        self.empresa_id = int(empresa_id)

    def _normalizar(self, texto):
        if not texto:
            return ""
        try:
            import unicodedata

            return (
                unicodedata.normalize("NFKD", str(texto))
                .encode("ascii", "ignore")
                .decode("ascii")
                .strip()
                .upper()
            )
        except Exception:
            return str(texto).strip().upper()

    @transaction.atomic
    def executar(self, *, descricao: str = "Orçamento gerado"):
        empresa = Empresas.objects.using(self.banco).get(empr_codi=self.empresa_id)

        alvo = self._normalizar(descricao)
        etapas = list(
            Etapavisita.objects.using(self.banco)
            .filter(etap_empr=empresa)
            .only("etap_id", "etap_nume", "etap_descricao")
        )

        for e in etapas:
            if self._normalizar(getattr(e, "etap_descricao", "")) == alvo:
                return e

        max_id = (
            Etapavisita.objects.using(self.banco)
            .aggregate(Max("etap_id"))
            .get("etap_id__max")
            or 0
        )
        novo_id = int(max_id) + 1

        max_nume = (
            Etapavisita.objects.using(self.banco)
            .filter(etap_empr=empresa)
            .aggregate(Max("etap_nume"))
            .get("etap_nume__max")
            or 0
        )
        novo_nume = int(max_nume) + 1

        return Etapavisita.objects.using(self.banco).create(
            etap_id=novo_id,
            etap_nume=novo_nume,
            etap_descricao=descricao,
            etap_empr=empresa,
            etap_obse=None,
        )
