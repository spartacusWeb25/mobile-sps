import json
from decimal import Decimal, InvalidOperation


def normalize_nfe_dict(raw: dict) -> dict:
    data = dict(raw or {})

    data["chave"] = _only_digits(data.get("chave"))[:44]
    data["tipo"] = (data.get("tipo") or "").strip().lower() or "entrada"

    data["emitente"] = _normalize_participante(data.get("emitente") or {})
    data["destinatario"] = _normalize_participante(data.get("destinatario") or {})
    data["ide"] = _normalize_simple_dict(data.get("ide") or {})
    data["total"] = _normalize_total(data.get("total") or {})
    data["info_adic"] = _normalize_simple_dict(data.get("info_adic") or {})
    data["cobr"] = _normalize_cobr(data.get("cobr") or {})
    data["itens"] = [_normalize_item(i) for i in (data.get("itens") or [])]

    return data


def dumps_json(data: dict) -> str:
    return json.dumps(data or {}, ensure_ascii=False, separators=(",", ":"))


def _normalize_participante(p: dict) -> dict:
    doc = _only_digits(p.get("documento"))
    cnpj = _only_digits(p.get("cnpj"))
    cpf = _only_digits(p.get("cpf"))
    if not doc:
        doc = cnpj or cpf

    ender = p.get("ender") or {}
    ender_norm = {
        "xLgr": (ender.get("xLgr") or "").strip(),
        "nro": (ender.get("nro") or "").strip() or "S/N",
        "xBairro": (ender.get("xBairro") or "").strip() or "CENTRO",
        "xMun": (ender.get("xMun") or "").strip(),
        "UF": (ender.get("UF") or "").strip().upper(),
        "CEP": _only_digits(ender.get("CEP"))[:8],
        "fone": _only_digits(ender.get("fone")),
    }

    return {
        "documento": doc,
        "cnpj": cnpj,
        "cpf": cpf,
        "nome": (p.get("nome") or "").strip(),
        "fantasia": (p.get("fantasia") or "").strip(),
        "ie": (p.get("ie") or "").strip(),
        "ender": ender_norm,
    }


def _normalize_item(item: dict) -> dict:
    item = dict(item or {})
    return {
        "nItem": str(item.get("nItem") or "").strip(),
        "cProd": str(item.get("cProd") or "").strip(),
        "cEAN": _only_digits(item.get("cEAN")),
        "xProd": str(item.get("xProd") or "").strip(),
        "NCM": _only_digits(item.get("NCM"))[:8],
        "CFOP": _only_digits(item.get("CFOP"))[:4],
        "CEST": _only_digits(item.get("CEST"))[:7],
        "uCom": str(item.get("uCom") or "").strip(),
        "qCom": _to_decimal_str(item.get("qCom")),
        "vUnCom": _to_decimal_str(item.get("vUnCom")),
        "vProd": _to_decimal_str(item.get("vProd")),
        "vDesc": _to_decimal_str(item.get("vDesc")),
        "xPed": str(item.get("xPed") or "").strip(),
        "nItemPed": _to_int_str(item.get("nItemPed")),
        "infAdProd": str(item.get("infAdProd") or "").strip(),
        "vTotTrib": _to_decimal_str(item.get("vTotTrib")),
        "vBCUFDest": _to_decimal_str(item.get("vBCUFDest")),
        "pICMSUFDest": _to_decimal_str(item.get("pICMSUFDest")),
        "vICMSUFDest": _to_decimal_str(item.get("vICMSUFDest")),
        "vFCPUFDest": _to_decimal_str(item.get("vFCPUFDest")),
        "pICMSInterPart": _to_decimal_str(item.get("pICMSInterPart")),
    }


def _normalize_total(total: dict) -> dict:
    total = dict(total or {})
    return {
        "vNF": _to_decimal_str(total.get("vNF")),
        "vProd": _to_decimal_str(total.get("vProd")),
        "vDesc": _to_decimal_str(total.get("vDesc")),
        "vTotTrib": _to_decimal_str(total.get("vTotTrib")),
        "vICMSUFDest": _to_decimal_str(total.get("vICMSUFDest")),
        "vFCPUFDest": _to_decimal_str(total.get("vFCPUFDest")),
    }


def _normalize_cobr(cobr: dict) -> dict:
    cobr = dict(cobr or {})
    fat = dict(cobr.get("fat") or {})
    return {
        "fat": {
            "nFat": str(fat.get("nFat") or "").strip(),
            "vOrig": _to_decimal_str(fat.get("vOrig")),
            "vDesc": _to_decimal_str(fat.get("vDesc")),
            "vLiq": _to_decimal_str(fat.get("vLiq")),
        },
        "dup": [
            {
                "nDup": str(item.get("nDup") or "").strip(),
                "dVenc": str(item.get("dVenc") or "").strip(),
                "vDup": _to_decimal_str(item.get("vDup")),
            }
            for item in (cobr.get("dup") or [])
            if item
        ],
    }


def _normalize_simple_dict(d: dict) -> dict:
    return {str(k): (str(v).strip() if v is not None else "") for k, v in (d or {}).items()}


def _to_decimal_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float, Decimal)):
        return str(Decimal(str(value)))
    s = str(value).strip().replace(",", ".")
    if not s:
        return ""
    try:
        return str(Decimal(s))
    except (InvalidOperation, ValueError):
        return ""


def _to_int_str(value) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        return str(int(Decimal(s)))
    except (InvalidOperation, ValueError):
        return ""


def _only_digits(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())

