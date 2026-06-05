 
import logging
from typing import List, Tuple, Optional
 
try:
    from pynfe.utils import FileUtils
except Exception:
    FileUtils = None
try:
    from pynfe.processamento.comunicacao import ComunicacaoSefaz
except Exception:
    ComunicacaoSefaz = None
 
logger = logging.getLogger(__name__)
 
 
class NotasDestinadasService:
    """
    Serviço de consulta de Notas Destinadas (Distribuição DF-e).
    """
 
    @classmethod
    def _get_certificado(cls, caminho_pfx: str, senha: str):
        """
        Carrega o certificado A1 quando disponível.
        """
        if FileUtils and hasattr(FileUtils, 'read_pfx'):
            return FileUtils.read_pfx(caminho_pfx, senha)
        return None
 
    @classmethod
    def _get_comunicacao(cls, uf: str, caminho_pfx: str, senha_pfx: str, ambiente: int = 1):
        """
        Cria o objeto de comunicação com a SEFAZ, com fallback quando a API varia.
        """
        if not ComunicacaoSefaz:
            raise RuntimeError('Biblioteca pynfe indisponível')
        homologacao = 2 if int(ambiente or 1) == 2 else 1
        return ComunicacaoSefaz(uf, caminho_pfx, senha_pfx, homologacao == 2)
 
    @classmethod
    def consultar_notas_destinadas(
        cls,
        *,
        uf: str,
        cnpj: str,
        ultimo_nsu: str,
        caminho_pfx: str,
        senha_pfx: str,
        ambiente: int = 1,
    ) -> Tuple[List[str], Optional[str]]:
        """
        Consulta DF-e e devolve:
        - lista de XMLs completos de NFe
        - novo_ultimo_nsu (para ser salvo e usado na próxima consulta)
        """
        com = cls._get_comunicacao(uf, caminho_pfx, senha_pfx, ambiente)
 
        import re
        import base64
        import gzip
        import xml.etree.ElementTree as ET
 
        cnpj_digits = re.sub(r"\D", "", str(cnpj))
        nsu_num = str(ultimo_nsu or '0')
        logger.info(f'Consultando DF-e para CNPJ={cnpj_digits} último_nsu={nsu_num}')
 
        resp = com.consulta_distribuicao(cnpj=cnpj_digits, nsu=nsu_num, consulta_nsu_especifico=False)
 
        xmls: List[str] = []
        novo_ultimo_nsu: Optional[str] = None
 
        try:
            texto = getattr(resp, 'text', None) or getattr(resp, 'content', b'')
            if isinstance(texto, bytes):
                texto = texto.decode('utf-8', errors='ignore')
            root = ET.fromstring(texto)
 
            def tag(t):
                return t.split('}')[-1]
 
            ret = None
            for e in root.iter():
                if tag(e.tag) == 'retDistDFeInt':
                    ret = e
                    break
            if ret is not None:
                for e in ret:
                    if tag(e.tag) == 'ultNSU':
                        novo_ultimo_nsu = (e.text or '').strip() or None
                    if tag(e.tag) == 'loteDistDFe':
                        for doc in e.iter():
                            if tag(doc.tag) == 'docZip':
                                schema = doc.attrib.get('schema')
                                conteudo = doc.text or ''
                                try:
                                    dados = base64.b64decode(conteudo)
                                    xml_str = gzip.decompress(dados).decode('utf-8', errors='ignore')
                                except Exception:
                                    xml_str = ''
                                if schema and schema.startswith('procNFe') and xml_str:
                                    xmls.append(xml_str)
        except Exception:
            pass
 
        logger.info(f'Retorno DF-e: {len(xmls)} XML(s) completos. novo_ultimo_nsu={novo_ultimo_nsu}')
        return xmls, novo_ultimo_nsu
 
 
class NfseDfeAdnService:
    @classmethod
    def _formatar_nsu(cls, nsu) -> str:
        return str(nsu or "0").strip().zfill(15)
 
    @classmethod
    def _criar_arquivos_pem_de_pfx(cls, caminho_pfx: str, senha_pfx: str) -> Tuple[str, str]:
        """
        Carrega certificado PFX e cria arquivos PEM temporários.
        """
        import os
        from core.util import carregar_certificado_pfx
 
        if not caminho_pfx or not os.path.isfile(caminho_pfx):
            raise ValueError("Certificado A1 (pfx) não encontrado no caminho")
  
        with open(caminho_pfx, "rb") as f:
            pfx_bytes = f.read()
  
        if not pfx_bytes:
            raise ValueError("Arquivo PFX está vazio")
  
        return carregar_certificado_pfx(pfx_bytes, senha_pfx)
 
    @classmethod
    def consultar_dfe(
        cls,
        *,
        nsu: str,
        caminho_pfx: str,
        senha_pfx: str,
        base_url: str = "https://adn.nfse.gov.br/contribuintes",
        timeout: int = 60,
    ) -> str:
        import os
        import requests
 
        nsu_fmt = cls._formatar_nsu(nsu)
        url = f"{(base_url or '').rstrip('/')}/DFe/{nsu_fmt}"
 
        cert_path = None
        key_path = None
        try:
            cert_path, key_path = cls._criar_arquivos_pem_de_pfx(caminho_pfx, senha_pfx)
            resp = requests.get(
                url,
                cert=(cert_path, key_path),
                headers={"Accept": "application/xml,text/xml,*/*;q=0.9"},
                timeout=int(timeout or 60),
            )
            if resp.status_code == 404:
                return ""
            resp.raise_for_status()
            raw = resp.content or b""
            if not raw:
                return ""

            encoding = resp.encoding or "utf-8"
            text = raw.decode(encoding, errors="replace")
            text = (text or "").lstrip("\ufeff").lstrip()

            return text
        finally:
            for p in [cert_path, key_path]:
                try:
                    if p and os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
 
    @classmethod
    def _parse_retorno(cls, xml_text: str):
        import base64
        import json
        import gzip
        import xml.etree.ElementTree as ET
 
        def tag(t: str) -> str:
            return (t or "").split("}")[-1]
 
        ult_nsu = None
        max_nsu = None
        docs = []
 
        xml_text = (xml_text or "").lstrip("\ufeff").lstrip()
        if xml_text.startswith("{") or xml_text.startswith("["):
            try:
                data = json.loads(xml_text)
            except Exception:
                inicio = (xml_text or "")[:200]
                raise ValueError(f"JSON inválido retornado pela ADN. body_inicio={inicio!r}")

            lote = None
            if isinstance(data, dict):
                lote = data.get("LoteDFe") or data.get("loteDFe") or data.get("loteDfe")
                ult_nsu = (
                    data.get("UltimoNSU")
                    or data.get("ultNSU")
                    or data.get("ult_nsu")
                    or data.get("UltNSU")
                    or ult_nsu
                )
                max_nsu = (
                    data.get("MaxNSU")
                    or data.get("maxNSU")
                    or data.get("max_nsu")
                    or data.get("MaiorNSU")
                    or data.get("maiorNSU")
                    or max_nsu
                )

            if not isinstance(lote, list):
                lote = []

            max_nsu_lote = None
            for item in lote:
                if not isinstance(item, dict):
                    continue
                nsu_item = item.get("NSU") or item.get("nsu")
                try:
                    nsu_item_int = int(str(nsu_item).strip())
                except Exception:
                    nsu_item_int = None
                if nsu_item_int is not None:
                    if max_nsu_lote is None or nsu_item_int > max_nsu_lote:
                        max_nsu_lote = nsu_item_int

                conteudo = (item.get("ArquivoXml") or item.get("arquivoXml") or item.get("arquivo_xml") or "").strip()
                xml_str = ""
                if conteudo:
                    try:
                        dados = base64.b64decode(conteudo)
                        try:
                            xml_str = gzip.decompress(dados).decode("utf-8", errors="ignore")
                        except Exception:
                            xml_str = dados.decode("utf-8", errors="ignore")
                    except Exception:
                        xml_str = ""

                docs.append(
                    {
                        "schema": (item.get("TipoDocumento") or item.get("tipoDocumento") or item.get("tipo_documento")),
                        "nsu": str(nsu_item).strip() if nsu_item is not None else None,
                        "xml": xml_str,
                    }
                )

            if not ult_nsu and max_nsu_lote is not None:
                ult_nsu = str(max_nsu_lote)

            return ult_nsu, max_nsu, docs

        try:
            root = ET.fromstring(xml_text or "<root/>")
        except ET.ParseError as e:
            inicio = (xml_text or "")[:200]
            raise ValueError(f"XML inválido retornado pela ADN. body_inicio={inicio!r}") from e

        for e in root.iter():
            t = tag(e.tag)
            if t == "ultNSU":
                ult_nsu = (e.text or "").strip() or None
            elif t == "maxNSU":
                max_nsu = (e.text or "").strip() or None
            elif t == "docZip":
                schema = (e.attrib.get("schema") or "").strip() or None
                nsu_attr = (e.attrib.get("NSU") or e.attrib.get("nsu") or "").strip() or None
                conteudo = (e.text or "").strip()
                xml_str = ""
                if conteudo:
                    try:
                        dados = base64.b64decode(conteudo)
                        try:
                            xml_str = gzip.decompress(dados).decode("utf-8", errors="ignore")
                        except Exception:
                            xml_str = dados.decode("utf-8", errors="ignore")
                    except Exception:
                        xml_str = ""
                docs.append(
                    {
                        "schema": schema,
                        "nsu": nsu_attr,
                        "xml": xml_str,
                    }
                )
 
        return ult_nsu, max_nsu, docs
 
    @classmethod
    def sincronizar(
        cls,
        *,
        ultimo_nsu: str = "0",
        caminho_pfx: str,
        senha_pfx: str,
        base_url: str = "https://adn.nfse.gov.br/contribuintes",
        timeout: int = 60,
        max_paginas: int = None,
    ):
        """
        Sincroniza documentos DFe em paginação.
        
        Usa certificado carregado via função central robusta.
        """
        nsu = cls._formatar_nsu(ultimo_nsu)
        paginas = 0
        ult_nsu = None
        max_nsu = None
        documentos = []
 
        logger.info(
            f"Iniciando sincronização DFe: "
            f"NSU inicial={nsu}, base_url={base_url}"
        )
 
        while True:
            try:
                xml = cls.consultar_dfe(
                    nsu=nsu,
                    caminho_pfx=caminho_pfx,
                    senha_pfx=senha_pfx,
                    base_url=base_url,
                    timeout=timeout,
                )
                ult_nsu, max_nsu, docs = cls._parse_retorno(xml)
                documentos.extend(docs)
                paginas += 1
 
                logger.info(
                    f"Página {paginas}: {len(docs)} docs, "
                    f"ultNSU={ult_nsu}, maxNSU={max_nsu}"
                )
 
                if ult_nsu and max_nsu and ult_nsu == max_nsu:
                    logger.info("Sincronização completa (ultNSU == maxNSU)")
                    break
 
                if max_paginas is not None and paginas >= int(max_paginas):
                    logger.info(f"Limite de páginas atingido: {paginas}")
                    break
 
                if not ult_nsu:
                    logger.info("Sem mais documentos (ultNSU vazio)")
                    break

                if docs:
                    try:
                        nsu = cls._formatar_nsu(int(str(ult_nsu).strip()) + 1)
                    except Exception:
                        nsu = cls._formatar_nsu(ult_nsu)
                else:
                    break
            except Exception as e:
                logger.error(f"Erro na sincronização página {paginas}: {e}")
                raise
 
        logger.info(
            f"Sincronização finalizada: "
            f"{len(documentos)} documentos, {paginas} páginas"
        )
        return documentos, ult_nsu, max_nsu, paginas


class NfseTomadasService:
    @classmethod
    def _localname(cls, tag: str) -> str:
        return (tag or "").split("}")[-1]

    @classmethod
    def _registrar_evento(cls, *, banco: str, empresa: int, filial: int, nfse_id: int, tipo: str, descricao: str = "") -> bool:
        from nfse.models import NfseEvento

        exists = (
            NfseEvento.objects.using(banco)
            .filter(
                nfsev_empr=int(empresa),
                nfsev_fili=int(filial),
                nfsev_nfse_id=int(nfse_id),
                nfsev_tip=str(tipo),
            )
            .exists()
        )
        if exists:
            return False

        NfseEvento.objects.using(banco).create(
            nfsev_empr=int(empresa),
            nfsev_fili=int(filial),
            nfsev_nfse_id=int(nfse_id),
            nfsev_tip=str(tipo),
            nfsev_desc=(descricao or None),
        )
        return True

    @classmethod
    def marcar_referenciada(cls, *, banco: str, empresa: int, filial: int, nfse_id: int) -> dict:
        from nfse.models import Nfse

        nfse = (
            Nfse.objects.using(banco)
            .filter(nfse_id=int(nfse_id), nfse_empr=int(empresa), nfse_fili=int(filial), nfse_statu="tomada")
            .first()
        )
        if not nfse:
            raise ValueError("NFS-e não encontrada")

        created = cls._registrar_evento(
            banco=banco,
            empresa=int(empresa),
            filial=int(filial),
            nfse_id=int(nfse_id),
            tipo="referenciada",
            descricao="NFS-e marcada como referenciada",
        )
        return {"nfse_id": int(nfse_id), "referenciada": True, "evento_criado": bool(created)}

    @classmethod
    def manifestar_ciencia(cls, *, banco: str, empresa: int, filial: int, nfse_id: int) -> dict:
        from nfse.models import Nfse

        nfse = (
            Nfse.objects.using(banco)
            .filter(nfse_id=int(nfse_id), nfse_empr=int(empresa), nfse_fili=int(filial), nfse_statu="tomada")
            .first()
        )
        if not nfse:
            raise ValueError("NFS-e não encontrada")

        cls._registrar_evento(
            banco=banco,
            empresa=int(empresa),
            filial=int(filial),
            nfse_id=int(nfse_id),
            tipo="referenciada",
            descricao="NFS-e marcada como referenciada",
        )

        created = cls._registrar_evento(
            banco=banco,
            empresa=int(empresa),
            filial=int(filial),
            nfse_id=int(nfse_id),
            tipo="ciencia",
            descricao="Ciência registrada",
        )
        return {"nfse_id": int(nfse_id), "ciencia": True, "evento_criado": bool(created)}

    @classmethod
    def _normalizar_doc(cls, v: str) -> str:
        if not v:
            return ""
        return "".join(ch for ch in str(v) if ch.isdigit())

    @classmethod
    def _to_decimal(cls, v):
        from decimal import Decimal

        if v is None:
            return Decimal("0")
        s = str(v).strip()
        if not s:
            return Decimal("0")
        s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 else s
        try:
            return Decimal(s)
        except Exception:
            return Decimal("0")

    @classmethod
    def _to_datetime(cls, v):
        from datetime import datetime

        s = (v or "").strip()
        if not s:
            return None
        try:
            if s.endswith("Z"):
                s = s[:-1]
            return datetime.fromisoformat(s)
        except Exception:
            pass
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s[:len(fmt)], fmt)
                return dt
            except Exception:
                continue
        return None

    @classmethod
    def _find_subtree(cls, root, names):
        names = {str(n).lower() for n in (names or [])}
        for el in root.iter():
            if cls._localname(el.tag).lower() in names:
                return el
        return None

    @classmethod
    def _find_text(cls, root, names):
        names = {str(n).lower() for n in (names or [])}
        for el in root.iter():
            if cls._localname(el.tag).lower() in names:
                txt = (el.text or "").strip()
                if txt:
                    return txt
        return ""

    @classmethod
    def _find_doc_e_nome(cls, root, bloco_names):
        bloco = cls._find_subtree(root, bloco_names)
        if bloco is None:
            return "", ""

        doc = cls._find_text(bloco, ["Cnpj", "CNPJ", "Cpf", "CPF", "Documento"])
        nome = cls._find_text(bloco, ["RazaoSocial", "xNome", "Nome", "NomeRazaoSocial", "NomeFantasia", "xFant"])
        return cls._normalizar_doc(doc), (nome or "").strip()

    @classmethod
    def _parse_nfse_xml(cls, xml_text: str):
        import xml.etree.ElementTree as ET

        root = ET.fromstring(xml_text or "<root/>")

        nfse_num = cls._find_text(root, ["NumeroNfse", "NumeroNFSe", "Numero", "nNFSe", "nNfse", "nfseNumero"])
        codigo_verificacao = cls._find_text(root, ["CodigoVerificacao", "CodigoVerificacaoNfse", "CodigoValidacao", "CodVerificacao"])

        prest_doc, prest_nome = cls._find_doc_e_nome(
            root,
            [
                "Prestador",
                "PrestadorServico",
                "PrestadorServicos",
                "DadosPrestador",
                "InfPrestador",
                "prest",
                "emit",
            ],
        )
        if not prest_nome:
            _doc, _nome = cls._find_doc_e_nome(root, ["emit", "Emitente", "DadosEmitente"])
            prest_doc = prest_doc or _doc
            prest_nome = prest_nome or _nome

        tom_doc, tom_nome = cls._find_doc_e_nome(
            root,
            [
                "Tomador",
                "TomadorServico",
                "TomadorServicos",
                "DadosTomador",
                "InfTomador",
                "toma",
                "tom",
            ],
        )

        data_emis = cls._find_text(root, ["DataEmissao", "dhEmi", "DtEmissao", "DataHoraEmissao", "DataEmissaoNfse"])
        dt = cls._to_datetime(data_emis)

        valor = (
            cls._find_text(root, ["ValorServicos", "ValorServicosNfse", "vServicos", "vServ", "vNFSe", "ValorNfse", "ValorLiquidoNfse"])
            or cls._find_text(root, ["ValorServicos", "ValorServicosNfse"])
        )
        valor_dec = cls._to_decimal(valor)

        desc_serv = cls._find_text(root, ["Discriminacao", "DiscriminacaoServico", "Descricao", "xServ", "DescricaoServico"])

        rps_num = cls._find_text(root, ["NumeroRps", "NumeroRPS", "nRps", "RpsNumero"])
        rps_seri = cls._find_text(root, ["SerieRps", "SerieRPS", "serieRps", "RpsSerie"])

        muni_codi = cls._find_text(root, ["CodigoMunicipio", "cMun", "CodigoMunicipioIncidencia", "CodMunicipio"])
        muni_nome = cls._find_text(root, ["Municipio", "NomeMunicipio", "xMun"])

        return {
            "numero": (nfse_num or "").strip(),
            "codigo_verificacao": (codigo_verificacao or "").strip(),
            "prest_doc": prest_doc,
            "prest_nome": prest_nome,
            "tom_doc": tom_doc,
            "tom_nome": tom_nome,
            "data_emissao": dt,
            "valor_serv": valor_dec,
            "serv_desc": (desc_serv or "").strip(),
            "rps_numero": (rps_num or "").strip(),
            "rps_serie": (rps_seri or "").strip(),
            "muni_codi": (muni_codi or "").strip(),
            "muni_nome": (muni_nome or "").strip(),
        }

    @classmethod
    def importar_tomadas(
        cls,
        *,
        banco: str,
        empresa: int,
        filial: int,
        documentos: list,
        tomador_doc: str = "",
    ):
        from nfse.models import Nfse

        tomador_doc = cls._normalizar_doc(tomador_doc)

        criadas = 0
        atualizadas = 0
        ids = []

        for d in (documentos or []):
            xml_text = (d or {}).get("xml") or ""
            xml_text = xml_text.strip()
            if not xml_text:
                continue

            try:
                info = cls._parse_nfse_xml(xml_text)
            except Exception:
                continue

            numero = info.get("numero") or ""
            prest_doc = info.get("prest_doc") or ""
            prest_nome = info.get("prest_nome") or "Prestador"
            tom_doc_xml = info.get("tom_doc") or tomador_doc
            tom_nome = info.get("tom_nome") or ""

            numero = numero.strip() or ""
            prest_doc = prest_doc.strip() or "0"
            tom_doc_xml = cls._normalizar_doc(tom_doc_xml) or tomador_doc or "0"

            rps_num = info.get("rps_numero") or numero or "0"
            serv_codi = "0000"
            serv_desc = info.get("serv_desc") or "NFS-e tomada"
            muni_codi = (info.get("muni_codi") or "").strip() or "0000000"

            defaults = {
                "nfse_empr": int(empresa),
                "nfse_fili": int(filial),
                "nfse_nume": numero or None,
                "nfse_rps_nume": str(rps_num),
                "nfse_rps_seri": info.get("rps_serie") or None,
                "nfse_codi_veri": info.get("codigo_verificacao") or None,
                "nfse_statu": "tomada",
                "nfse_muni_codi": str(muni_codi),
                "nfse_muni_nome": info.get("muni_nome") or None,
                "nfse_pres_doc": str(prest_doc),
                "nfse_pres_nome": str(prest_nome)[:120],
                "nfse_tom_doc": str(tom_doc_xml),
                "nfse_tom_nome": str(tom_nome)[:120] if tom_nome else None,
                "nfse_serv_codi": str(serv_codi),
                "nfse_serv_desc": str(serv_desc) if serv_desc else "NFS-e tomada",
                "nfse_val_serv": info.get("valor_serv") or 0,
                "nfse_data_emis": info.get("data_emissao"),
                "nfse_xml_ret": xml_text,
            }

            obj = (
                Nfse.objects.using(banco)
                .filter(
                    nfse_empr=int(empresa),
                    nfse_fili=int(filial),
                    nfse_nume=(numero or None),
                    nfse_tom_doc=str(tom_doc_xml),
                    nfse_statu="tomada",
                )
                .first()
            )

            if obj:
                Nfse.objects.using(banco).filter(nfse_id=int(obj.nfse_id)).update(**defaults)
                created = False
                obj = Nfse.objects.using(banco).filter(nfse_id=int(obj.nfse_id)).first()
            else:
                obj, created = Nfse.objects.using(banco).update_or_create(
                    defaults=defaults,
                    nfse_empr=int(empresa),
                    nfse_fili=int(filial),
                    nfse_nume=(numero or None),
                    nfse_tom_doc=str(tom_doc_xml),
                    nfse_statu="tomada",
                )

            ids.append(int(obj.nfse_id))
            if created:
                criadas += 1
            else:
                atualizadas += 1

        return {
            "criadas": criadas,
            "atualizadas": atualizadas,
            "ids": ids,
        }

    @classmethod
    def gerar_contas_pagar(
        cls,
        *,
        banco: str,
        nfse_id: int,
        empresa: int,
        filial: int,
        usuario_id: int = 0,
        data_base=None,
        parcelas: int = 1,
        intervalo_dias: int = 30,
    ):
        from datetime import date, timedelta
        from django.db import transaction
        from django.db.models import Q, Max
        from contas_a_pagar.models import Titulospagar
        from Entidades.models import Entidades
        from nfse.models import Nfse

        nfse = (
            Nfse.objects.using(banco)
            .filter(nfse_id=int(nfse_id), nfse_empr=int(empresa), nfse_fili=int(filial), nfse_statu="tomada")
            .first()
        )
        if not nfse:
            raise ValueError("NFS-e não encontrada")

        prest_doc = cls._normalizar_doc(getattr(nfse, "nfse_pres_doc", "") or "")
        if not prest_doc or prest_doc == "0":
            raise ValueError("Documento do prestador não encontrado na NFS-e")

        fornecedor = Entidades.objects.using(banco).filter(
            enti_empr=int(empresa)
        ).filter(
            Q(enti_cnpj=prest_doc) | Q(enti_cpf=prest_doc)
        ).first()
        if not fornecedor:
            prest_nome = (getattr(nfse, "nfse_pres_nome", "") or "").strip() or str(prest_doc)

            ultimo_codigo = Entidades.objects.using(banco).aggregate(Max("enti_clie"))["enti_clie__max"] or 0
            try:
                novo_codigo = int(ultimo_codigo) + 1
            except Exception:
                novo_codigo = 1

            while Entidades.objects.using(banco).filter(enti_clie=int(novo_codigo)).exists():
                novo_codigo = int(novo_codigo) + 1

            dados = {
                "enti_empr": int(empresa),
                "enti_clie": int(novo_codigo),
                "enti_nome": prest_nome[:100],
                "enti_fant": prest_nome[:100],
                "enti_tipo_enti": "FO",
                "enti_cep": "",
                "enti_ende": "",
                "enti_nume": "",
                "enti_cida": "",
                "enti_esta": "",
                "enti_bair": "",
            }

            if len(prest_doc) == 14:
                dados["enti_cnpj"] = prest_doc
            elif len(prest_doc) == 11:
                dados["enti_cpf"] = prest_doc

            fornecedor = Entidades.objects.using(banco).create(**dados)

        fornecedor_id = int(getattr(fornecedor, "enti_clie"))
        numero = str(getattr(nfse, "nfse_nume", "") or getattr(nfse, "nfse_rps_nume", "") or "").strip() or str(nfse_id)
        serie = "NFSE"

        total = getattr(nfse, "nfse_val_serv", 0) or 0
        total_dec = cls._to_decimal(total)
        if total_dec <= 0:
            raise ValueError("Valor da NFS-e inválido para gerar contas a pagar")

        try:
            parcelas_int = int(parcelas or 1)
        except Exception:
            parcelas_int = 1
        if parcelas_int < 1:
            parcelas_int = 1

        try:
            intervalo_int = int(intervalo_dias or 30)
        except Exception:
            intervalo_int = 30
        if intervalo_int < 0:
            intervalo_int = 0

        if data_base is None:
            dt_emis = getattr(nfse, "nfse_data_emis", None)
            data_base = dt_emis.date() if dt_emis else date.today()

        valor_parcela = (total_dec / parcelas_int) if parcelas_int else total_dec

        titulos = []
        with transaction.atomic(using=banco):
            for i in range(1, parcelas_int + 1):
                venc = data_base + timedelta(days=(i - 1) * intervalo_int)
                parc = str(i)
                existe = Titulospagar.objects.using(banco).filter(
                    titu_empr=int(empresa),
                    titu_fili=int(filial),
                    titu_forn=int(fornecedor_id),
                    titu_tipo="Entrada",
                    titu_titu=str(numero),
                    titu_seri=str(serie),
                    titu_parc=str(parc),
                ).first()
                if existe:
                    continue

                titulo = Titulospagar.objects.using(banco).create(
                    titu_empr=int(empresa),
                    titu_fili=int(filial),
                    titu_forn=int(fornecedor_id),
                    titu_tipo="Entrada",
                    titu_titu=str(numero),
                    titu_parc=str(parc),
                    titu_seri=str(serie),
                    titu_valo=valor_parcela,
                    titu_venc=venc,
                    titu_emis=data_base,
                    titu_aber="A",
                    titu_usua_lanc=int(usuario_id or 0),
                    titu_hist=f"NFS-e {numero} (tomada) - Parc {parc}",
                )
                titulos.append(titulo)

        cls._registrar_evento(
            banco=banco,
            empresa=int(empresa),
            filial=int(filial),
            nfse_id=int(nfse_id),
            tipo="referenciada",
            descricao="Referenciada ao gerar contas a pagar",
        )

        return {
            "nfse_id": int(nfse_id),
            "titulos_criados": len(titulos),
        }
