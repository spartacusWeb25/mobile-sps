from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connections, transaction
from django.db.utils import OperationalError

from Pisos.models import Itenspedidospisos, Itensorcapisos, Orcamentopisos, Pedidospisos
from Pisos.services.orcamento_atualizar_service import OrcamentoAtualizarService
from Pisos.services.orcamento_criar_service import OrcamentoCriarService
from Pisos.services.orcamento_exportar_service import OrcamentoExportarPedidoService
from Pisos.services.pedido_atualizar_service import PedidoAtualizarService


def _montar_db_config(lic: dict) -> dict:
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": lic["db_name"],
        "USER": lic["db_user"],
        "PASSWORD": lic["db_password"],
        "HOST": lic["db_host"],
        "PORT": lic["db_port"],
        "OPTIONS": {
            "connect_timeout": 30,
            "application_name": "validar_pisos_tenancy",
        },
        "CONN_MAX_AGE": 60,
        "ATOMIC_REQUESTS": False,
        "AUTOCOMMIT": True,
    }


@dataclass(frozen=True)
class _RunItem:
    filial: int
    orcamento_nume: int
    pedido_nume: int


class Command(BaseCommand):
    help = "Valida isolamento por empresa/filial na criação de orçamentos e exportação para pedidos (dry-run por padrão)."

    @staticmethod
    def _snapshot_numero(*, banco: str, empresa: int, filiais: list[int], numero: int) -> dict:
        return {
            "orc_exists": {
                f: Orcamentopisos.objects.using(banco).filter(orca_empr=empresa, orca_fili=f, orca_nume=numero).count()
                for f in filiais
            },
            "ped_exists": {
                f: Pedidospisos.objects.using(banco).filter(pedi_empr=empresa, pedi_fili=f, pedi_nume=numero).count()
                for f in filiais
            },
            "orc_itens": {
                f: Itensorcapisos.objects.using(banco).filter(item_empr=empresa, item_fili=f, item_orca=numero).count()
                for f in filiais
            },
            "ped_itens": {
                f: Itenspedidospisos.objects.using(banco).filter(item_empr=empresa, item_fili=f, item_pedi=numero).count()
                for f in filiais
            },
        }

    @staticmethod
    def _proximo_orcamento_numero(*, banco: str, empresa: int, filial: int) -> int:
        ultimo = (
            Orcamentopisos.objects.using(banco)
            .filter(orca_empr=empresa, orca_fili=filial)
            .order_by("-orca_nume")
            .first()
        )
        return int(ultimo.orca_nume + 1) if ultimo else 1

    def _validar_sem_efeito_colateral(
        self,
        *,
        erros: list[str],
        etapa: str,
        before: dict,
        after: dict,
        filiais: list[int],
        filial_alvo: int,
    ) -> None:
        for chave in ("orc_exists", "ped_exists", "orc_itens", "ped_itens"):
            for filial in filiais:
                if filial == filial_alvo:
                    continue
                if before[chave][filial] != after[chave][filial]:
                    erros.append(
                        f"{etapa}: alterou indevidamente fili={filial} em {chave} ({before[chave][filial]} -> {after[chave][filial]})"
                    )

    @staticmethod
    def _somar_itens_orcamento(*, banco: str, empresa: int, filial: int, numero: int) -> Decimal:
        total = Decimal("0")
        for item in Itensorcapisos.objects.using(banco).filter(
            item_empr=empresa,
            item_fili=filial,
            item_orca=numero,
        ):
            total += Decimal(str(getattr(item, "item_suto", 0) or 0))
        return total

    @staticmethod
    def _somar_itens_pedido(*, banco: str, empresa: int, filial: int, numero: int) -> Decimal:
        total = Decimal("0")
        for item in Itenspedidospisos.objects.using(banco).filter(
            item_empr=empresa,
            item_fili=filial,
            item_pedi=numero,
        ):
            total += Decimal(str(getattr(item, "item_suto", 0) or 0))
        return total

    def _validar_orcamento(
        self,
        *,
        banco: str,
        empresa: int,
        filial: int,
        numero: int,
        qtd_itens: int,
        erros: list[str],
    ) -> None:
        orcamento = Orcamentopisos.objects.using(banco).filter(
            orca_empr=empresa,
            orca_fili=filial,
            orca_nume=numero,
        ).first()
        if orcamento is None:
            erros.append(f"Orçamento não encontrado: empr={empresa} fili={filial} orca_nume={numero}")
            return

        itens_qtd = Itensorcapisos.objects.using(banco).filter(
            item_empr=empresa,
            item_fili=filial,
            item_orca=numero,
        ).count()
        if itens_qtd != qtd_itens:
            erros.append(
                f"Qtd itens orçamento divergente: empr={empresa} fili={filial} orca={numero} qtd={itens_qtd} esperado={qtd_itens}"
            )

    def _validar_pedido(
        self,
        *,
        banco: str,
        empresa: int,
        filial: int,
        numero: int,
        qtd_itens: int,
        erros: list[str],
    ) -> None:
        pedido = Pedidospisos.objects.using(banco).filter(
            pedi_empr=empresa,
            pedi_fili=filial,
            pedi_nume=numero,
        ).first()
        if pedido is None:
            erros.append(f"Pedido não encontrado: empr={empresa} fili={filial} pedi_nume={numero}")
            return

        itens_qtd = Itenspedidospisos.objects.using(banco).filter(
            item_empr=empresa,
            item_fili=filial,
            item_pedi=numero,
        ).count()
        if itens_qtd != qtd_itens:
            erros.append(
                f"Qtd itens pedido divergente: empr={empresa} fili={filial} pedi={numero} qtd={itens_qtd} esperado={qtd_itens}"
            )

    def add_arguments(self, parser):
        parser.add_argument("--database", dest="database", required=False)
        parser.add_argument("--tenant", dest="tenant", required=False, help="Slug do tenant. Ex: saveweb001")
        parser.add_argument("--slug", dest="slug", required=False, help="Alias de --tenant (compatibilidade).")
        parser.add_argument("--empresa", dest="empresa", type=int, required=True)
        parser.add_argument("--filiais", dest="filiais", required=True, help="Lista separada por vírgula. Ex: 1,2,3,4")
        parser.add_argument("--qtd", dest="qtd", type=int, default=100)
        parser.add_argument("--commit", dest="commit", action="store_true", default=False)

    def handle(self, *args, **options):
        slug = (options.get("tenant") or options.get("slug") or "").strip()
        if slug:
            from core.licencas_loader import carregar_licencas_dict

            licencas = carregar_licencas_dict() or []
            lic = next((l for l in licencas if str(l.get("slug") or "").strip() == slug), None)
            if not lic:
                raise ValueError(f"Nenhuma licença encontrada para tenant={slug}")

            alias = f"tenant_{slug}"
            if alias not in connections.databases:
                connections.databases[alias] = _montar_db_config(lic)

            try:
                with connections[alias].cursor() as cursor:
                    cursor.execute("SELECT 1")
            except OperationalError as e:
                raise ValueError(f"[{alias}] Banco de dados inacessível: {e}")

            banco = alias
        else:
            banco = str(options.get("database") or "").strip()
            if not banco:
                raise ValueError("Informe --database ou --tenant/--slug.")

        empresa = int(options["empresa"])
        qtd = int(options["qtd"])
        commit = bool(options["commit"])

        self.stdout.write(f"Banco: {banco}")
        self.stdout.write("Commit: " + ("SIM" if commit else "NÃO (dry-run com rollback)"))

        filiais_raw = str(options["filiais"] or "").strip()
        filiais = [int(x.strip()) for x in filiais_raw.split(",") if x.strip()]
        if not filiais:
            raise ValueError("Informe --filiais com ao menos um valor.")

        itens_orcamento_inicial = [
            {
                "item_prod": "TESTE",
                "item_quan": Decimal("2"),
                "item_unit": Decimal("10"),
                "item_ambi": 1,
            },
            {
                "item_prod": "TESTE2",
                "item_quan": Decimal("1"),
                "item_unit": Decimal("15"),
                "item_ambi": 2,
            },
        ]
        itens_orcamento_editado = [
            {
                "item_prod": "TESTE",
                "item_quan": Decimal("3"),
                "item_unit": Decimal("11"),
                "item_ambi": 1,
            },
            {
                "item_prod": "TESTE3",
                "item_quan": Decimal("2"),
                "item_unit": Decimal("7"),
                "item_ambi": 2,
            },
            {
                "item_prod": "TESTE4",
                "item_quan": Decimal("1"),
                "item_unit": Decimal("9"),
                "item_ambi": 3,
            },
        ]
        itens_orcamento_pos_export = [
            {
                "item_prod": "TESTE5",
                "item_quan": Decimal("4"),
                "item_unit": Decimal("6"),
                "item_ambi": 1,
            }
        ]
        itens_pedido_editado = [
            {
                "item_prod": "TESTE6",
                "item_quan": Decimal("5"),
                "item_unit": Decimal("8"),
                "item_ambi": 1,
            },
            {
                "item_prod": "TESTE7",
                "item_quan": Decimal("1"),
                "item_unit": Decimal("13"),
                "item_ambi": 2,
            },
        ]

        criados: list[_RunItem] = []
        erros: list[str] = []

        with transaction.atomic(using=banco):
            for idx in range(qtd):
                filial = filiais[idx % len(filiais)]
                try:
                    if idx and idx % 10 == 0:
                        self.stdout.write(f"Progresso: {idx}/{qtd}")

                    numero_previsto = self._proximo_orcamento_numero(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                    )
                    snapshot = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero_previsto,
                    )

                    orcamento = OrcamentoCriarService().executar(
                        banco=banco,
                        dados={
                            "orca_empr": empresa,
                            "orca_fili": filial,
                            "orca_clie": None,
                            "orca_desc": Decimal("0"),
                            "orca_fret": Decimal("0"),
                            "orca_cred": Decimal("0"),
                        },
                        itens=itens_orcamento_inicial,
                    )

                    numero = int(orcamento.orca_nume)
                    snapshot_after_create = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    self._validar_sem_efeito_colateral(
                        erros=erros,
                        etapa="Criar orçamento",
                        before=snapshot,
                        after=snapshot_after_create,
                        filiais=filiais,
                        filial_alvo=filial,
                    )
                    self._validar_orcamento(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                        numero=numero,
                        qtd_itens=len(itens_orcamento_inicial),
                        erros=erros,
                    )

                    snapshot_before_orc_update = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    OrcamentoAtualizarService().executar(
                        banco=banco,
                        orcamento=orcamento,
                        dados={
                            "orca_desc": Decimal("1"),
                            "orca_fret": Decimal("2"),
                            "orca_cred": Decimal("0"),
                            "parametros": {},
                        },
                        itens=itens_orcamento_editado,
                    )
                    snapshot_after_orc_update = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    self._validar_sem_efeito_colateral(
                        erros=erros,
                        etapa="Alterar orçamento antes da exportação",
                        before=snapshot_before_orc_update,
                        after=snapshot_after_orc_update,
                        filiais=filiais,
                        filial_alvo=filial,
                    )
                    self._validar_orcamento(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                        numero=numero,
                        qtd_itens=len(itens_orcamento_editado),
                        erros=erros,
                    )

                    pedido_nume = OrcamentoExportarPedidoService().executar(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                        numero=numero,
                    )

                    criados.append(
                        _RunItem(
                            filial=filial,
                            orcamento_nume=numero,
                            pedido_nume=int(pedido_nume),
                        )
                    )

                    snapshot_after_export = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    self._validar_sem_efeito_colateral(
                        erros=erros,
                        etapa="Exportar orçamento para pedido",
                        before=snapshot_after_orc_update,
                        after=snapshot_after_export,
                        filiais=filiais,
                        filial_alvo=filial,
                    )
                    self._validar_pedido(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                        numero=int(pedido_nume),
                        qtd_itens=len(itens_orcamento_editado),
                        erros=erros,
                    )

                    orcamento_db = Orcamentopisos.objects.using(banco).get(
                        orca_empr=empresa,
                        orca_fili=filial,
                        orca_nume=numero,
                    )
                    pedido_db = Pedidospisos.objects.using(banco).get(
                        pedi_empr=empresa,
                        pedi_fili=filial,
                        pedi_nume=int(pedido_nume),
                    )
                    if int(getattr(orcamento_db, "orca_pedi", 0) or 0) != int(pedido_nume):
                        erros.append(
                            f"Vínculo orçamento->pedido divergente: empr={empresa} fili={filial} orca={numero} orca_pedi={getattr(orcamento_db, 'orca_pedi', None)} pedido={pedido_nume}"
                        )
                    if int(getattr(pedido_db, "pedi_orca", 0) or 0) != numero:
                        erros.append(
                            f"Vínculo pedido->orçamento divergente: empr={empresa} fili={filial} pedi={pedido_nume} pedi_orca={getattr(pedido_db, 'pedi_orca', None)} orca={numero}"
                        )

                    snapshot_before_orc_pos_export = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    OrcamentoAtualizarService().executar(
                        banco=banco,
                        orcamento=orcamento_db,
                        dados={
                            "orca_desc": Decimal("0"),
                            "orca_fret": Decimal("0"),
                            "orca_cred": Decimal("0"),
                            "parametros": {},
                        },
                        itens=itens_orcamento_pos_export,
                    )
                    snapshot_after_orc_pos_export = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    self._validar_sem_efeito_colateral(
                        erros=erros,
                        etapa="Alterar orçamento após exportação",
                        before=snapshot_before_orc_pos_export,
                        after=snapshot_after_orc_pos_export,
                        filiais=filiais,
                        filial_alvo=filial,
                    )
                    self._validar_orcamento(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                        numero=numero,
                        qtd_itens=len(itens_orcamento_pos_export),
                        erros=erros,
                    )
                    self._validar_pedido(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                        numero=int(pedido_nume),
                        qtd_itens=len(itens_orcamento_editado),
                        erros=erros,
                    )

                    snapshot_before_pedido_update = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    PedidoAtualizarService().executar(
                        banco=banco,
                        pedido=pedido_db,
                        dados={
                            "pedi_desc": Decimal("0"),
                            "pedi_fret": Decimal("0"),
                            "pedi_cred": Decimal("0"),
                            "parametros": {},
                        },
                        itens=itens_pedido_editado,
                    )
                    snapshot_after_pedido_update = self._snapshot_numero(
                        banco=banco,
                        empresa=empresa,
                        filiais=filiais,
                        numero=numero,
                    )
                    self._validar_sem_efeito_colateral(
                        erros=erros,
                        etapa="Alterar pedido",
                        before=snapshot_before_pedido_update,
                        after=snapshot_after_pedido_update,
                        filiais=filiais,
                        filial_alvo=filial,
                    )
                    self._validar_pedido(
                        banco=banco,
                        empresa=empresa,
                        filial=filial,
                        numero=int(pedido_nume),
                        qtd_itens=len(itens_pedido_editado),
                        erros=erros,
                    )
                except Exception as e:
                    erros.append(f"[{idx}] filial={filial}: {e}")

            for reg in criados:
                self._validar_orcamento(
                    banco=banco,
                    empresa=empresa,
                    filial=reg.filial,
                    numero=reg.orcamento_nume,
                    qtd_itens=len(itens_orcamento_pos_export),
                    erros=erros,
                )
                self._validar_pedido(
                    banco=banco,
                    empresa=empresa,
                    filial=reg.filial,
                    numero=reg.pedido_nume,
                    qtd_itens=len(itens_pedido_editado),
                    erros=erros,
                )

            if not commit:
                transaction.set_rollback(True, using=banco)


        total_criados = len(criados)
        total_erros = len(erros)

        if erros:
            for e in erros[:50]:
                self.stderr.write(e)
            if total_erros > 50:
                self.stderr.write(f"... ({total_erros - 50} erros omitidos)")

        self.stdout.write(f"Orçamentos exportados: {total_criados}/{qtd}")
        self.stdout.write(f"Erros: {total_erros}")
        self.stdout.write("Commit: " + ("SIM" if commit else "NÃO (dry-run com rollback)"))
