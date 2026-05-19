from django.db import connections, transaction
from django.db.models import Max

from planogerencial.models import PlanoGerencialMascara, PlanoGerencialConta
from planogerencial.services.mascara_service import MascaraGerencialService


class PlanoGerencialService:
    def __init__(self, *, empresa, db_alias="default"):
        self.empresa = int(empresa)
        self.db_alias = db_alias

    def get_mascara_ativa(self):
        mascara = (
            PlanoGerencialMascara.objects.using(self.db_alias)
            .filter(gere_empr=self.empresa, gere_ativ=True)
            .first()
        )

        if not mascara:
            raise ValueError("Nenhuma máscara gerencial ativa encontrada.")

        return mascara

    def listar(self):
        return (
            PlanoGerencialConta.objects.using(self.db_alias)
            .filter(gere_empr=self.empresa)
            .order_by("gere_expa", "gere_redu")
        )

    def buscar_por_reduzido(self, redu):
        return (
            PlanoGerencialConta.objects.using(self.db_alias)
            .filter(gere_empr=self.empresa, gere_redu=redu)
            .first()
        )

    def proximo_reduzido(self):
        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(MAX(gere_redu), 0) + 1
                FROM planocontasgerencial
                WHERE gere_empr = %s
                """,
                [self.empresa],
            )
            return cursor.fetchone()[0]

    def _proximo_codigo_raiz(self, niveis):
        digitos = MascaraGerencialService.get_digitos_por_nivel(niveis, 1)

        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT gere_expa
                FROM planocontasgerencial
                WHERE gere_empr = %s
                  AND gere_nive = 1
                  AND gere_expa IS NOT NULL
                """,
                [self.empresa],
            )
            rows = cursor.fetchall()

        usados = []

        for row in rows:
            try:
                usados.append(int(str(row[0]).split(".")[0]))
            except Exception:
                pass

        proximo = max(usados) + 1 if usados else 1
        return str(proximo).zfill(digitos)

    def _proximo_codigo_filho(self, pai, niveis):
        partes_pai = str(pai.gere_expa).split(".")
        nivel_filho = len(partes_pai) + 1

        if nivel_filho > MascaraGerencialService.total_niveis(niveis):
            raise ValueError("Esta conta já está no último nível da máscara.")

        if pai.gere_anal == "A":
            raise ValueError("Conta analítica não pode receber filhos.")

        digitos_filho = MascaraGerencialService.get_digitos_por_nivel(
            niveis,
            nivel_filho,
        )

        prefixo = f"{pai.gere_expa}."

        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(
                """
                SELECT gere_expa
                FROM planocontasgerencial
                WHERE gere_empr = %s
                  AND gere_nive = %s
                  AND gere_expa LIKE %s
                """,
                [self.empresa, nivel_filho, f"{prefixo}%"],
            )
            rows = cursor.fetchall()

        usados = []

        for row in rows:
            try:
                partes = str(row[0]).split(".")
                usados.append(int(partes[nivel_filho - 1]))
            except Exception:
                pass

        proximo = max(usados) + 1 if usados else 1
        sufixo = str(proximo).zfill(digitos_filho)

        return f"{pai.gere_expa}.{sufixo}"

    def _montar_grupo(self, codigo):
        partes = str(codigo).split(".")
        return ".".join(partes[:2]) if len(partes) >= 2 else partes[0]

    def _montar_niv1(self, codigo):
        try:
            return int(str(codigo).split(".")[0])
        except Exception:
            return None

    def _insert_conta(self, dados):
        with connections[self.db_alias].cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO planocontasgerencial (
                    gere_empr,
                    gere_redu,
                    gere_nome,
                    gere_expa,
                    gere_nive,
                    gere_anal,
                    gere_grup,
                    gere_niv1,
                    gere_inat
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    dados["gere_empr"],
                    dados["gere_redu"],
                    dados["gere_nome"],
                    dados["gere_expa"],
                    dados["gere_nive"],
                    dados["gere_anal"],
                    dados["gere_grup"],
                    dados["gere_niv1"],
                    dados["gere_inat"],
                ],
            )

    @transaction.atomic
    def criar(self, *, nome, parent_redu=None):
        mascara = self.get_mascara_ativa()
        niveis = MascaraGerencialService.normalizar_niveis(mascara.gere_nive)

        if parent_redu:
            pai = self.buscar_por_reduzido(parent_redu)

            if not pai:
                raise ValueError("Conta pai não encontrada.")

            codigo = self._proximo_codigo_filho(pai, niveis)
        else:
            pai = None
            codigo = self._proximo_codigo_raiz(niveis)

        nivel = len(codigo.split("."))
        tipo = MascaraGerencialService.get_tipo_por_nivel(niveis, nivel)
        redu = self.proximo_reduzido()

        dados = {
            "gere_empr": self.empresa,
            "gere_redu": redu,
            "gere_nome": nome,
            "gere_expa": codigo,
            "gere_nive": nivel,
            "gere_anal": tipo,
            "gere_grup": self._montar_grupo(codigo),
            "gere_niv1": self._montar_niv1(codigo),
            "gere_inat": False,
        }

        self._insert_conta(dados)

        return self.buscar_por_reduzido(redu)