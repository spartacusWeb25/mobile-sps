# notas_fiscais/services/itens_service.py

from django.db import transaction, connections
from django.core.exceptions import ValidationError

from ..models import NotaItem, NotaItemImposto
from ..handlers.itens_handler import ItensHandler
from Produtos.models import Produtos
from core.utils import calcular_total_item_com_desconto


class ItensService:
    _columns_cache = {}

    @staticmethod
    def _get_table_columns(db_alias: str, table_name: str) -> set:
        cache_key = (db_alias or "default", table_name)
        cached = ItensService._columns_cache.get(cache_key)
        if cached is not None:
            return cached
        cols = set()
        try:
            with connections[db_alias].cursor() as cursor:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                    [table_name],
                )
                cols = {r[0] for r in cursor.fetchall()}
        except Exception:
            cols = set()
        ItensService._columns_cache[cache_key] = cols
        return cols

    @staticmethod
    def _ensure_nf_nota_item_schema(db_alias: str) -> None:
        try:
            if connections[db_alias].vendor != "postgresql":
                return
        except Exception:
            return

        cols = ItensService._get_table_columns(db_alias, "nf_nota_item")
        missing = {"beneficio_fiscal", "ibscbs_cst", "ibscbs_cclasstrib"} - set(cols or [])
        if not missing:
            return

        try:
            with connections[db_alias].cursor() as cursor:
                if "beneficio_fiscal" in missing:
                    cursor.execute("ALTER TABLE nf_nota_item ADD COLUMN IF NOT EXISTS beneficio_fiscal varchar(10) NULL;")
                if "ibscbs_cst" in missing:
                    cursor.execute("ALTER TABLE nf_nota_item ADD COLUMN IF NOT EXISTS ibscbs_cst varchar(3) NULL;")
                if "ibscbs_cclasstrib" in missing:
                    cursor.execute("ALTER TABLE nf_nota_item ADD COLUMN IF NOT EXISTS ibscbs_cclasstrib varchar(6) NULL;")
            ItensService._columns_cache.pop((db_alias or "default", "nf_nota_item"), None)
        except Exception:
            return

    @staticmethod
    def inserir_itens(nota, itens, impostos_map=None):
        """
        Cria os itens e seus impostos.
        impostos_map → dict {index_item: dados_impostos}
        """

        ItensHandler.validar_itens(itens)
        itens_norm = ItensHandler.normalizar_itens(itens)

        db_alias = getattr(getattr(nota, "_state", None), "db", None) or "default"
        empresa_id = getattr(nota, "empresa", None)
        ItensService._ensure_nf_nota_item_schema(db_alias)

        from CFOP.services.services import MotorFiscal, get_empresa_uf_origem
        from CFOP.models import CFOP, NcmFiscalPadrao

        uf_origem = get_empresa_uf_origem(
            empresa_id=getattr(nota, "empresa", None),
            filial_id=getattr(nota, "filial", None),
            banco=db_alias,
        )

        dest = getattr(nota, "destinatario", None)
        uf_destino = (getattr(dest, "enti_esta", None) or "").strip()
        if not uf_destino and getattr(nota, "destinatario_id", None):
            from Entidades.models import Entidades

            dest = (
                Entidades.objects.using(db_alias)
                .filter(pk=nota.destinatario_id)
                .first()
            )
            uf_destino = (getattr(dest, "enti_esta", None) or "").strip()

        if not uf_destino:
            uf_destino = uf_origem

        def mapear_tipo_operacao(n):
            if getattr(n, "tipo_operacao", None) == 1:
                if getattr(n, "finalidade", None) == 4:
                    return "DEVOLUCAO_COMPRA"
                return "VENDA"
            if getattr(n, "finalidade", None) == 4:
                return "DEVOLUCAO_VENDA"
            return "COMPRA"

        tipo_oper = mapear_tipo_operacao(nota)
        motor = MotorFiscal(banco=db_alias)

        for index, item_data in enumerate(itens_norm):
            prod_val = item_data.get("produto")
            if prod_val and not isinstance(prod_val, Produtos):
                qs = Produtos.objects.using(db_alias).filter(prod_codi=str(prod_val))
                if empresa_id is not None:
                    qs = qs.filter(prod_empr=str(empresa_id))
                try:
                    produto_obj = qs.get()
                except Produtos.MultipleObjectsReturned:
                    raise ValidationError(
                        f"Produto {prod_val} possui múltiplos cadastros para a empresa {empresa_id}."
                    )
                except Produtos.DoesNotExist:
                    raise ValidationError(
                        f"Produto {prod_val} não encontrado para a empresa {empresa_id}."
                    )
                item_data["produto"] = produto_obj
            
            model_fields = {f.name for f in NotaItem._meta.get_fields()}
            model_fields.discard("nota")
            model_fields.discard("id")
            clean_data = {k: v for k, v in item_data.items() if k in model_fields}
            table_cols = ItensService._get_table_columns(db_alias, "nf_nota_item")
            if table_cols:
                allowed_field_names = {
                    f.name for f in NotaItem._meta.fields
                    if f.name not in ("id",) and getattr(f, "column", None) in table_cols
                }
                allowed_field_names.discard("nota")
                clean_data = {k: v for k, v in clean_data.items() if k in allowed_field_names}

            produto_obj = item_data.get("produto")
            if isinstance(produto_obj, Produtos):
                if ("ncm" in model_fields) and (not str(clean_data.get("ncm") or "").strip()):
                    ncm_raw = str(getattr(produto_obj, "prod_ncm", "") or "")
                    ncm_digits = "".join(ch for ch in ncm_raw if ch.isdigit())[:8]
                    if ncm_digits:
                        clean_data["ncm"] = ncm_digits

                if ("cfop" in model_fields) and (not str(clean_data.get("cfop") or "").strip()):
                    cfop_por_ncm = None
                    ncm_obj = motor.obter_ncm(produto_obj)
                    if ncm_obj:
                        def _match_padrao(fiscal):
                            fiscal_uf_origem = (getattr(fiscal, "uf_origem", None) or "").strip().upper()
                            fiscal_uf_destino = (getattr(fiscal, "uf_destino", None) or "").strip().upper()
                            fiscal_tipo_entidade = (getattr(fiscal, "tipo_entidade", None) or "").strip().upper()

                            ctx_uf_origem = (uf_origem or "").strip().upper()
                            ctx_uf_destino = (uf_destino or "").strip().upper()
                            ctx_tipo_entidade = (getattr(dest, "enti_tipo_enti", None) or "").strip().upper()

                            if fiscal_uf_origem and (not ctx_uf_origem or fiscal_uf_origem != ctx_uf_origem):
                                return False
                            if fiscal_uf_destino and (not ctx_uf_destino or fiscal_uf_destino != ctx_uf_destino):
                                return False
                            if fiscal_tipo_entidade:
                                if not ctx_tipo_entidade:
                                    return False
                                if ctx_tipo_entidade == "AM":
                                    return True
                                if fiscal_tipo_entidade == "AM":
                                    return True
                                if fiscal_tipo_entidade != ctx_tipo_entidade:
                                    return False

                            return True

                        fiscals_ncm = NcmFiscalPadrao.objects.using(db_alias).filter(ncm_id=ncm_obj.pk)
                        best = None
                        best_score = -1
                        for fiscal in fiscals_ncm:
                            if not _match_padrao(fiscal):
                                continue
                            if not getattr(fiscal, "cfop", None):
                                continue
                            score = 0
                            if (getattr(fiscal, "uf_origem", None) or "").strip():
                                score += 1
                            if (getattr(fiscal, "uf_destino", None) or "").strip():
                                score += 1
                            if (getattr(fiscal, "tipo_entidade", None) or "").strip():
                                score += 1
                            if score > best_score:
                                best = fiscal
                                best_score = score

                        if best and getattr(best, "cfop", None):
                            cfop_code = str(getattr(best, "cfop") or "").strip()
                            cfop_code = "".join(ch for ch in cfop_code if ch.isdigit())
                            if len(cfop_code) == 4:
                                cfop_por_ncm = (
                                    CFOP.objects.using(db_alias)
                                    .filter(cfop_codi=cfop_code, cfop_empr=getattr(nota, "empresa", None))
                                    .first()
                                    or CFOP.objects.using(db_alias).filter(cfop_codi=cfop_code).first()
                                )

                    cfop_obj = cfop_por_ncm or motor.resolver_cfop(tipo_oper, uf_origem, uf_destino)
                    if cfop_obj and getattr(cfop_obj, "cfop_codi", None):
                        clean_data["cfop"] = str(cfop_obj.cfop_codi).strip()

            quantidade = clean_data.get("quantidade") or 0
            unitario = clean_data.get("unitario") or 0
            desconto = clean_data.get("desconto") or 0
            if "total_item" in model_fields and "total_item" not in clean_data:
                clean_data["total_item"] = calcular_total_item_com_desconto(
                    quantidade, unitario, desconto
                )

            item_obj = NotaItem.objects.using(db_alias).create(nota=nota, **clean_data)

            # impostos
            if impostos_map and index in impostos_map:
                imp_raw = impostos_map[index]
                imp_norm = ItensHandler.normalizar_impostos(imp_raw)

                NotaItemImposto.objects.using(db_alias).create(item=item_obj, **imp_norm)


    @staticmethod
    def atualizar_itens(nota, itens, impostos_map=None):
        """
        Remove tudo e recria.
        Mais simples e consistente para notas fiscais.
        """

        db_alias = getattr(getattr(nota, "_state", None), "db", None) or "default"
        NotaItem.objects.using(db_alias).filter(nota=nota).delete()

        ItensService.inserir_itens(nota, itens, impostos_map)
