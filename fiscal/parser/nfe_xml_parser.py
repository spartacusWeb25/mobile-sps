from fiscal.utils.xml_utils import (
    extract_chave_from_inf,
    find_inf_nfe_node,
    find_nfe_node,
    nsmap_for,
    only_digits,
    parse_xml,
    xpath_text,
)


def parse_nfe(xml_content: str) -> dict:
    root = parse_xml(xml_content)
    nfe_node = find_nfe_node(root)
    if nfe_node is None:
        nfe_node = root

    inf_node = find_inf_nfe_node(nfe_node)
    if inf_node is None:
        inf_node = nfe_node
    nsmap = nsmap_for(inf_node)

    chave = extract_chave_from_inf(inf_node)
    tp_nf = xpath_text(inf_node, "string(./nfe:ide/nfe:tpNF)", nsmap=nsmap, default="").strip()
    tipo = "entrada" if tp_nf == "0" else "saida"

    ide = {
        "tpNF": tp_nf,
        "nNF": xpath_text(inf_node, "string(./nfe:ide/nfe:nNF)", nsmap=nsmap, default="").strip(),
        "serie": xpath_text(inf_node, "string(./nfe:ide/nfe:serie)", nsmap=nsmap, default="").strip(),
        "dhEmi": xpath_text(inf_node, "string(./nfe:ide/nfe:dhEmi)", nsmap=nsmap, default="").strip()
        or xpath_text(inf_node, "string(./nfe:ide/nfe:dEmi)", nsmap=nsmap, default="").strip(),
        "natOp": xpath_text(inf_node, "string(./nfe:ide/nfe:natOp)", nsmap=nsmap, default="").strip(),
    }

    emit = _parse_participante(inf_node, nsmap, base_xpath="./nfe:emit", ender_xpath="./nfe:enderEmit")
    dest = _parse_participante(inf_node, nsmap, base_xpath="./nfe:dest", ender_xpath="./nfe:enderDest")

    total = {
        "vNF": xpath_text(inf_node, "string(./nfe:total/nfe:ICMSTot/nfe:vNF)", nsmap=nsmap, default="").strip(),
        "vProd": xpath_text(inf_node, "string(./nfe:total/nfe:ICMSTot/nfe:vProd)", nsmap=nsmap, default="").strip(),
        "vDesc": xpath_text(inf_node, "string(./nfe:total/nfe:ICMSTot/nfe:vDesc)", nsmap=nsmap, default="").strip(),
        "vTotTrib": xpath_text(inf_node, "string(./nfe:total/nfe:ICMSTot/nfe:vTotTrib)", nsmap=nsmap, default="").strip(),
        "vICMSUFDest": xpath_text(inf_node, "string(./nfe:total/nfe:ICMSTot/nfe:vICMSUFDest)", nsmap=nsmap, default="").strip(),
        "vFCPUFDest": xpath_text(inf_node, "string(./nfe:total/nfe:ICMSTot/nfe:vFCPUFDest)", nsmap=nsmap, default="").strip(),
    }

    info_adic = {
        "infCpl": xpath_text(inf_node, "string(./nfe:infAdic/nfe:infCpl)", nsmap=nsmap, default="").strip(),
    }

    cobr = {
        "fat": {
            "nFat": xpath_text(inf_node, "string(./nfe:cobr/nfe:fat/nfe:nFat)", nsmap=nsmap, default="").strip(),
            "vOrig": xpath_text(inf_node, "string(./nfe:cobr/nfe:fat/nfe:vOrig)", nsmap=nsmap, default="").strip(),
            "vDesc": xpath_text(inf_node, "string(./nfe:cobr/nfe:fat/nfe:vDesc)", nsmap=nsmap, default="").strip(),
            "vLiq": xpath_text(inf_node, "string(./nfe:cobr/nfe:fat/nfe:vLiq)", nsmap=nsmap, default="").strip(),
        },
        "dup": [],
    }
    for dup in inf_node.xpath("./nfe:cobr/nfe:dup", namespaces=nsmap) if nsmap else inf_node.findall(".//dup"):
        cobr["dup"].append(
            {
                "nDup": xpath_text(dup, "string(./nfe:nDup)", nsmap=nsmap, default="").strip(),
                "dVenc": xpath_text(dup, "string(./nfe:dVenc)", nsmap=nsmap, default="").strip(),
                "vDup": xpath_text(dup, "string(./nfe:vDup)", nsmap=nsmap, default="").strip(),
            }
        )

    itens = []
    for det in inf_node.xpath("./nfe:det", namespaces=nsmap) if nsmap else inf_node.findall(".//det"):
        prod = det.xpath("./nfe:prod", namespaces=nsmap)[0] if nsmap else det.find(".//prod")
        if prod is None:
            continue
        imposto = det.xpath("./nfe:imposto", namespaces=nsmap)[0] if nsmap else det.find(".//imposto")
        icms_uf_dest = None
        if imposto is not None:
            nodes = imposto.xpath("./nfe:ICMSUFDest", namespaces=nsmap) if nsmap else imposto.findall("./ICMSUFDest")
            icms_uf_dest = nodes[0] if nodes else None

        itens.append(
            {
                "nItem": (det.get("nItem") or "").strip(),
                "cProd": xpath_text(prod, "string(./nfe:cProd)", nsmap=nsmap, default="").strip(),
                "cEAN": only_digits(xpath_text(prod, "string(./nfe:cEAN)", nsmap=nsmap, default="").strip()),
                "xProd": xpath_text(prod, "string(./nfe:xProd)", nsmap=nsmap, default="").strip(),
                "NCM": only_digits(xpath_text(prod, "string(./nfe:NCM)", nsmap=nsmap, default="").strip())[:8],
                "CFOP": only_digits(xpath_text(prod, "string(./nfe:CFOP)", nsmap=nsmap, default="").strip())[:4],
                "CEST": only_digits(xpath_text(prod, "string(./nfe:CEST)", nsmap=nsmap, default="").strip())[:7],
                "uCom": xpath_text(prod, "string(./nfe:uCom)", nsmap=nsmap, default="").strip(),
                "qCom": xpath_text(prod, "string(./nfe:qCom)", nsmap=nsmap, default="").strip(),
                "vUnCom": xpath_text(prod, "string(./nfe:vUnCom)", nsmap=nsmap, default="").strip(),
                "vProd": xpath_text(prod, "string(./nfe:vProd)", nsmap=nsmap, default="").strip(),
                "vDesc": xpath_text(prod, "string(./nfe:vDesc)", nsmap=nsmap, default="").strip(),
                "xPed": xpath_text(prod, "string(./nfe:xPed)", nsmap=nsmap, default="").strip(),
                "nItemPed": xpath_text(prod, "string(./nfe:nItemPed)", nsmap=nsmap, default="").strip(),
                "infAdProd": xpath_text(det, "string(./nfe:infAdProd)", nsmap=nsmap, default="").strip(),
                "vTotTrib": xpath_text(imposto, "string(./nfe:vTotTrib)", nsmap=nsmap, default="").strip(),
                "vBCUFDest": xpath_text(icms_uf_dest, "string(./nfe:vBCUFDest)", nsmap=nsmap, default="").strip(),
                "pICMSUFDest": xpath_text(icms_uf_dest, "string(./nfe:pICMSUFDest)", nsmap=nsmap, default="").strip(),
                "vICMSUFDest": xpath_text(icms_uf_dest, "string(./nfe:vICMSUFDest)", nsmap=nsmap, default="").strip(),
                "vFCPUFDest": xpath_text(icms_uf_dest, "string(./nfe:vFCPUFDest)", nsmap=nsmap, default="").strip(),
                "pICMSInterPart": xpath_text(icms_uf_dest, "string(./nfe:pICMSInterPart)", nsmap=nsmap, default="").strip(),
            }
        )

    return {
        "chave": chave,
        "tipo": tipo,
        "ide": ide,
        "emitente": emit,
        "destinatario": dest,
        "total": total,
        "info_adic": info_adic,
        "cobr": cobr,
        "itens": itens,
    }


def _parse_participante(inf_node, nsmap, *, base_xpath: str, ender_xpath: str) -> dict:
    base_node_list = inf_node.xpath(base_xpath, namespaces=nsmap) if nsmap else []
    base_node = base_node_list[0] if base_node_list else None
    ender_node_list = inf_node.xpath(ender_xpath, namespaces=nsmap) if nsmap else []
    ender_node = ender_node_list[0] if ender_node_list else None

    cnpj = only_digits(xpath_text(base_node, "string(./nfe:CNPJ)", nsmap=nsmap, default="").strip())
    cpf = only_digits(xpath_text(base_node, "string(./nfe:CPF)", nsmap=nsmap, default="").strip())
    doc = cnpj or cpf

    return {
        "documento": doc,
        "cnpj": cnpj,
        "cpf": cpf,
        "nome": xpath_text(base_node, "string(./nfe:xNome)", nsmap=nsmap, default="").strip(),
        "fantasia": xpath_text(base_node, "string(./nfe:xFant)", nsmap=nsmap, default="").strip(),
        "ie": xpath_text(base_node, "string(./nfe:IE)", nsmap=nsmap, default="").strip(),
        "ender": {
            "xLgr": xpath_text(ender_node, "string(./nfe:xLgr)", nsmap=nsmap, default="").strip(),
            "nro": xpath_text(ender_node, "string(./nfe:nro)", nsmap=nsmap, default="").strip(),
            "xBairro": xpath_text(ender_node, "string(./nfe:xBairro)", nsmap=nsmap, default="").strip(),
            "xMun": xpath_text(ender_node, "string(./nfe:xMun)", nsmap=nsmap, default="").strip(),
            "UF": xpath_text(ender_node, "string(./nfe:UF)", nsmap=nsmap, default="").strip(),
            "CEP": only_digits(xpath_text(ender_node, "string(./nfe:CEP)", nsmap=nsmap, default="").strip())[:8],
            "fone": only_digits(xpath_text(ender_node, "string(./nfe:fone)", nsmap=nsmap, default="").strip()),
        },
    }

