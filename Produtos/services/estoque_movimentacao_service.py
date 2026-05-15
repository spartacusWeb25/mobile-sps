from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from Entradas_Estoque.models import EntradaEstoque
from Saidas_Estoque.models import SaidasEstoque
from Produtos.models import SaldoProduto, Produtos


class EstoqueMovimentacaoService:
    @staticmethod
    def _to_decimal(value):
        if value is None or value == "":
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        s = str(value).strip().replace(".", "").replace(",", ".")
        try:
            return Decimal(s)
        except Exception:
            return Decimal("0")

    @staticmethod
    def _get_saldo(banco, *, empresa_id, filial_id, produto_codigo):
        produto = Produtos.objects.using(banco).filter(prod_empr=str(empresa_id), prod_codi=str(produto_codigo)).first()
        if not produto:
            return None
        saldo = SaldoProduto.objects.using(banco).filter(
            produto_codigo=produto,
            empresa=str(empresa_id),
            filial=str(filial_id),
        ).first()
        return saldo.saldo_estoque if saldo else None

    @staticmethod
    def registrar_entrada(
        banco,
        *,
        empresa_id,
        filial_id,
        produto_codigo,
        quantidade,
        total,
        entidade=None,
        observacao="",
        data=None,
        usuario_id=0,
    ):
        qtd = EstoqueMovimentacaoService._to_decimal(quantidade)
        tot = EstoqueMovimentacaoService._to_decimal(total)
        if qtd <= 0:
            raise ValueError("Quantidade deve ser maior que zero.")
        if tot < 0:
            raise ValueError("Total inválido.")

        data_mov = data or timezone.localdate()
        if isinstance(data_mov, str):
            data_mov = timezone.datetime.fromisoformat(data_mov).date()

        ent = (str(entidade).strip()[:10] if entidade else None) or None
        obs = (str(observacao or "").strip()[:100]) or ""

        with transaction.atomic(using=banco):
            existente = EntradaEstoque.objects.using(banco).filter(
                entr_empr=int(empresa_id),
                entr_fili=int(filial_id),
                entr_prod=str(produto_codigo)[:10],
                entr_data=data_mov,
            ).first()
            if existente:
                existente.entr_quan = (existente.entr_quan or 0) + qtd
                existente.entr_tota = (existente.entr_tota or 0) + tot
                if ent:
                    existente.entr_enti = ent
                if obs:
                    existente.entr_obse = obs
                existente.entr_usua = int(usuario_id or 0)
                existente.save(using=banco)
                saldo = EstoqueMovimentacaoService._get_saldo(
                    banco, empresa_id=empresa_id, filial_id=filial_id, produto_codigo=produto_codigo
                )
                return {"tipo": "ENTRADA", "id": existente.entr_sequ, "saldo": saldo}

            proximo = (EntradaEstoque.objects.using(banco).aggregate(Max("entr_sequ"))["entr_sequ__max"] or 0) + 1
            obj = EntradaEstoque.objects.using(banco).create(
                entr_sequ=int(proximo),
                entr_empr=int(empresa_id),
                entr_fili=int(filial_id),
                entr_prod=str(produto_codigo)[:10],
                entr_enti=ent,
                entr_data=data_mov,
                entr_unit=None,
                entr_quan=qtd,
                entr_tota=tot,
                entr_obse=obs,
                entr_usua=int(usuario_id or 0),
            )
            saldo = EstoqueMovimentacaoService._get_saldo(
                banco, empresa_id=empresa_id, filial_id=filial_id, produto_codigo=produto_codigo
            )
            return {"tipo": "ENTRADA", "id": obj.entr_sequ, "saldo": saldo}

    @staticmethod
    def registrar_saida(
        banco,
        *,
        empresa_id,
        filial_id,
        produto_codigo,
        quantidade,
        total,
        entidade=None,
        observacao="",
        data=None,
        usuario_id=0,
    ):
        qtd = EstoqueMovimentacaoService._to_decimal(quantidade)
        tot = EstoqueMovimentacaoService._to_decimal(total)
        if qtd <= 0:
            raise ValueError("Quantidade deve ser maior que zero.")
        if tot < 0:
            raise ValueError("Total inválido.")

        data_mov = data or timezone.localdate()
        if isinstance(data_mov, str):
            data_mov = timezone.datetime.fromisoformat(data_mov).date()

        ent = (str(entidade).strip()[:10] if entidade else None) or None
        obs = (str(observacao or "").strip()[:100]) or ""

        with transaction.atomic(using=banco):
            proximo = (SaidasEstoque.objects.using(banco).aggregate(Max("said_sequ"))["said_sequ__max"] or 0) + 1
            try:
                obj = SaidasEstoque.objects.using(banco).create(
                    said_sequ=int(proximo),
                    said_empr=int(empresa_id),
                    said_fili=int(filial_id),
                    said_prod=str(produto_codigo)[:10],
                    said_enti=ent,
                    said_data=data_mov,
                    said_quan=qtd,
                    said_tota=tot,
                    said_obse=obs,
                    said_usua=int(usuario_id or 0),
                )
            except IntegrityError:
                existente = SaidasEstoque.objects.using(banco).filter(
                    said_empr=int(empresa_id),
                    said_fili=int(filial_id),
                    said_prod=str(produto_codigo)[:10],
                    said_data=data_mov,
                ).first()
                if not existente:
                    raise
                existente.said_quan = (existente.said_quan or 0) + qtd
                existente.said_tota = (existente.said_tota or 0) + tot
                if ent:
                    existente.said_enti = ent
                if obs:
                    existente.said_obse = obs
                existente.said_usua = int(usuario_id or 0)
                existente.save(using=banco)
                saldo = EstoqueMovimentacaoService._get_saldo(
                    banco, empresa_id=empresa_id, filial_id=filial_id, produto_codigo=produto_codigo
                )
                return {"tipo": "SAIDA", "id": existente.said_sequ, "saldo": saldo}

            saldo = EstoqueMovimentacaoService._get_saldo(
                banco, empresa_id=empresa_id, filial_id=filial_id, produto_codigo=produto_codigo
            )
            return {"tipo": "SAIDA", "id": obj.said_sequ, "saldo": saldo}

