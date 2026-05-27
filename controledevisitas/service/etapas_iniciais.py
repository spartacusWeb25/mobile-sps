# Pisos/services/status_pisos_seed_service.py

from ..constants import ETAPS_VISITAS_PADRAO    
from controledevisitas.models import Etapavisita


class EtapavisitasIniciais:

    @staticmethod
    def criar_padrao(banco, empr):
        registros = []

        for item in ETAPS_VISITAS_PADRAO:
            registros.append(Etapavisita(
                etap_empr=empr,
                etap_id=item["etap_id"],
                etap_nume = item["etap_id"],
                etap_descricao=item["etap_descricao"],
                etap_cor=item["etap_cor"],
            ))
        return Etapavisita.objects.using(banco).bulk_create(
            registros,
            ignore_conflicts=True
        )