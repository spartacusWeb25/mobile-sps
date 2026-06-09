from Licencas.models import Filiais
from Entidades.models import Entidades

from ..models import ProdutoFiscalPadrao
from ..models_tributos import Tributos
from .tributos_service import TributoService


def _norm_upper(v):
    return v.strip().upper() if isinstance(v, str) else ""


def _match_produto_fiscal(fiscal, *, uf_origem=None, uf_destino=None, tipo_entidade=None) -> bool:
    if not fiscal:
        return False

    fiscal_uf_origem = _norm_upper(getattr(fiscal, "uf_origem", None))
    fiscal_uf_destino = _norm_upper(getattr(fiscal, "uf_destino", None))
    fiscal_tipo_entidade = _norm_upper(getattr(fiscal, "tipo_entidade", None))

    ctx_uf_origem = _norm_upper(uf_origem)
    ctx_uf_destino = _norm_upper(uf_destino)
    ctx_tipo_entidade = _norm_upper(tipo_entidade)

    if fiscal_uf_origem:
        if not ctx_uf_origem or fiscal_uf_origem != ctx_uf_origem:
            return False

    if fiscal_uf_destino:
        if not ctx_uf_destino or fiscal_uf_destino != ctx_uf_destino:
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


def obter_status_fiscal_produtos(
    *,
    banco: str,
    empresa: int,
    filial: int,
    produtos_codigos: list[str],
    cliente_id: int | None = None,
    tipo_entidade: str | None = None,
    uf_destino: str | None = None,
):
    produtos_codigos = [str(c or "").strip() for c in (produtos_codigos or []) if str(c or "").strip()]
    produtos_codigos = list(dict.fromkeys(produtos_codigos))
    if not produtos_codigos:
        return {}

    banco = banco or "default"

    if cliente_id and (not tipo_entidade or not uf_destino):
        cliente = (
            Entidades.objects.using(banco)
            .filter(enti_empr=int(empresa), enti_clie=int(cliente_id))
            .values("enti_tipo_enti", "enti_esta")
            .first()
        )
        if cliente:
            tipo_entidade = tipo_entidade or (cliente.get("enti_tipo_enti") or "")
            uf_destino = uf_destino or (cliente.get("enti_esta") or "")

    tipo_entidade = (tipo_entidade or "").strip().upper() or None
    uf_destino = (uf_destino or "").strip().upper() or None

    filial_obj = (
        Filiais.objects.using(banco)
        .defer("empr_cert_digi")
        .filter(empr_empr=int(empresa), empr_codi=int(filial))
        .values("empr_esta")
        .first()
    )
    uf_origem = (filial_obj or {}).get("empr_esta")
    uf_origem = (uf_origem or "").strip().upper() or None

    out = {
        c: {
            "ok": False,
            "fonte": None,
            "detalhe": None,
            "tipo_entidade": tipo_entidade,
            "uf_destino": uf_destino,
        }
        for c in produtos_codigos
    }

    if uf_destino:
        candidates = TributoService(banco, int(empresa), int(filial))._entity_candidates(tipo_entidade)
        trib_rows = list(
            Tributos.objects.using(banco)
            .filter(
                trib_empr=int(empresa),
                trib_fili=int(filial),
                trib_tipo="P",
                trib_codi__in=produtos_codigos,
                trib_esta=uf_destino,
            )
            .values("trib_codi", "trib_enti")
        )
        if trib_rows:
            by_codigo = {}
            for r in trib_rows:
                codigo = str(r.get("trib_codi") or "").strip()
                enti = str(r.get("trib_enti") or "").strip().upper()
                if not codigo:
                    continue
                by_codigo.setdefault(codigo, set()).add(enti)
            for codigo, entities in by_codigo.items():
                if any(e in candidates for e in entities):
                    out[codigo]["ok"] = True
                    out[codigo]["fonte"] = "SPARTACUS"
                    out[codigo]["detalhe"] = f"Tributação Spartacus ({uf_destino}/{tipo_entidade or '000'})"

    fiscals = list(
        ProdutoFiscalPadrao.objects.using(banco)
        .filter(produto__prod_codi__in=produtos_codigos)
        .select_related("produto")
    )
    fiscal_map = {str(getattr(f.produto, "prod_codi", "") or "").strip(): f for f in fiscals}

    for codigo in list(out.keys()):
        if out[codigo]["ok"]:
            continue
        fiscal = fiscal_map.get(codigo)
        if fiscal and _match_produto_fiscal(fiscal, uf_origem=uf_origem, uf_destino=uf_destino, tipo_entidade=tipo_entidade):
            out[codigo]["ok"] = True
            out[codigo]["fonte"] = "PRODUTO"
            out[codigo]["detalhe"] = "Fiscal padrão do produto"

    for codigo, info in out.items():
        if info["ok"]:
            continue
        if not tipo_entidade or not uf_destino:
            info["detalhe"] = "Contexto fiscal incompleto (cliente sem UF/tipo)"
        else:
            info["detalhe"] = "Sem fiscal padrão por produto/tipo (vai cair em NCM/CFOP)"

    return out
