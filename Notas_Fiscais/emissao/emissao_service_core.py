import os
import logging
from datetime import datetime

from dotenv import load_dotenv
from lxml import etree

from .assinatura import AssinadorA1Service
from .sefaz_client import SefazClient
from .parser import SefazResponseParser
from .gerador_xml import GeradorXML, NFE_NS
from .urls_sefaz import URLS_SEFAZ
from .exceptions import ErroEmissao

logger = logging.getLogger(__name__)
load_dotenv()


def montar_envi_nfe(xml_assinado: str, id_lote: str) -> str:
    NFE_NS = "http://www.portalfiscal.inf.br/nfe"

    root = etree.fromstring(xml_assinado.encode("utf-8"))

    if not root.tag.startswith("{"):
        nfe = etree.Element(f"{{{NFE_NS}}}NFe")
        nfe.append(root)
        xml_nfe = etree.tostring(nfe, encoding="utf-8").decode()
    else:
        xml_nfe = xml_assinado

    id_lote_fmt = (id_lote or "1").zfill(15)

    return (
        f'<enviNFe xmlns="{NFE_NS}" versao="4.00">'
        f'<idLote>{id_lote_fmt}</idLote>'
        f'<indSinc>1</indSinc>'
        f'{xml_nfe}'
        f'</enviNFe>'
    )


class EmissaoServiceCore:

    UF_MAP = {
        "RO": "11", "AC": "12", "AM": "13", "RR": "14",
        "PA": "15", "AP": "16", "TO": "17",
        "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25",
        "PE": "26", "AL": "27", "SE": "28", "BA": "29",
        "MG": "31", "ES": "32", "RJ": "33", "SP": "35",
        "PR": "41", "SC": "42", "RS": "43",
        "MS": "50", "MT": "51", "GO": "52", "DF": "53"
    }

    def __init__(self, dto: dict, filial):
        self.dto = dto
        self.filial = filial
        self.ambiente = int(filial.empr_ambi_nfe or 2)

    # =====================================================================
    # FLUXO PRINCIPAL
    # =====================================================================
    def emitir(self):
        emit = self.dto["emitente"]
        logger.debug("EmissaoServiceCore.emitir: DTO inicial recebido: %s", self.dto)

        if "cUF" not in emit or not emit["cUF"]:
            emit["cUF"] = self._uf_to_cuf(emit["uf"])

        if "cNF" not in self.dto:
            self.dto["cNF"] = self._gerar_cnf()

        if "chave" not in self.dto:
            self.dto["chave"] = self._gerar_chave(self.dto)

        xml_gerado = GeradorXML().gerar(self.dto)
        logger.debug("EmissaoServiceCore.emitir: XML base gerado: %s", xml_gerado)

        # FIX: _load_certificado retorna (pfx_bytes, senha) — bytes puros.
        # AssinadorA1Service.__init__ valida isinstance(pfx_bytes, (bytes, bytearray))
        # e opera inteiramente em memória via pkcs12. Nunca passar path aqui.
        pfx_bytes, pfx_pass = self._load_certificado()
        assinador = AssinadorA1Service(pfx_bytes, pfx_pass)
        xml_assinado = assinador.assinar_xml(xml_gerado)

        xml_enviado = montar_envi_nfe(
            xml_assinado=xml_assinado,
            id_lote=str(self.dto.get("numero") or 1),
        )

        url = self._resolve_url()

        # FIX: o método correto é _extract_key_and_cert(), não _extract_keys().
        # Retorna (key_pem, cert_chain_pem) — SefazClient usa cert + key PEM para TLS.
        key_pem, cert_chain_pem = assinador._extract_key_and_cert()

        logger.debug("EmissaoServiceCore.emitir: XML enviNFe montado: %s", xml_enviado)

        resposta_xml = SefazClient(
            cert_pem=cert_chain_pem,
            key_pem=key_pem,
            url=url,
            verify=self._resolve_verify(),
        ).enviar_xml(xml_enviado)

        resposta = SefazResponseParser().parse(resposta_xml)

        return resposta, xml_assinado, resposta_xml

    # =====================================================================
    # CHAVE E cNF
    # =====================================================================
    def _gerar_cnf(self):
        import random
        return str(random.randint(0, 99999999)).zfill(8)

    def _uf_to_cuf(self, uf: str) -> str:
        return self.UF_MAP.get(uf.upper(), "00")

    def _gerar_chave(self, dto: dict) -> str:
        emit = dto["emitente"]
        cUF = emit["cUF"]

        dh_emi_str = dto.get("data_emissao")
        if dh_emi_str:
            try:
                if "T" in dh_emi_str:
                    dt = datetime.fromisoformat(dh_emi_str)
                else:
                    dt = datetime.strptime(dh_emi_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                aamm = dt.strftime("%y%m")
            except Exception:
                aamm = datetime.now().strftime("%y%m")
        else:
            aamm = datetime.now().strftime("%y%m")

        cnpj = emit["cnpj"].zfill(14)
        mod = str(dto.get("modelo", "55")).zfill(2)
        serie = str(dto.get("serie", 1)).zfill(3)
        numero = str(dto["numero"]).zfill(9)
        tpEmis = "1"
        cNF = dto["cNF"]

        base = f"{cUF}{aamm}{cnpj}{mod}{serie}{numero}{tpEmis}{cNF}"
        dv = self._calcular_dv(base)
        return base + str(dv)

    def _calcular_dv(self, base: str):
        pesos = [2, 3, 4, 5, 6, 7, 8, 9]
        soma = 0
        for i, dig in enumerate(reversed(base)):
            soma += int(dig) * pesos[i % 8]
        resto = soma % 11
        dv = 11 - resto
        return 0 if dv >= 10 else dv

    # =====================================================================
    # CERTIFICADO
    # Retorna (pfx_bytes: bytes, senha: str) — sempre bytes puros.
    # AssinadorA1Service opera inteiramente em memória, não precisa de arquivo.
    # =====================================================================
    def _load_certificado(self) -> tuple[bytes, str]:
        import base64

        pfx_bytes = None

        # 1) Tenta blob do banco (bytea → memoryview → bytes)
        try:
            if hasattr(self.filial, 'empr_cert_digi') and self.filial.empr_cert_digi:
                pfx_bytes = bytes(self.filial.empr_cert_digi)
        except Exception:
            pass

        # 2) Fallback: lê de arquivo em disco
        if not pfx_bytes:
            caminho = getattr(self.filial, 'empr_cert', None)
            if caminho and os.path.isfile(caminho):
                with open(caminho, 'rb') as f:
                    pfx_bytes = f.read()
                logger.info(
                    "Certificado carregado de arquivo: %s empresa=%s filial=%s",
                    caminho,
                    getattr(self.filial, 'empr_empr', '?'),
                    getattr(self.filial, 'empr_codi', '?'),
                )

        if not pfx_bytes:
            raise ErroEmissao("Filial não possui certificado digital (nem banco, nem arquivo).")

        # 3) Detecta se o blob foi gravado em base64 no banco.
        # PFX/P12 válido começa sempre com os magic bytes ASN.1: 0x30 0x82.
        # Se não começar assim, tenta decodificar como base64 e valida novamente.
        if not pfx_bytes[:2] == b'\x30\x82':
            try:
                decoded = base64.b64decode(pfx_bytes)
                if decoded[:2] == b'\x30\x82':
                    logger.info(
                        "Certificado estava em base64 no banco — decodificado: %d → %d bytes",
                        len(pfx_bytes),
                        len(decoded),
                    )
                    pfx_bytes = decoded
            except Exception:
                pass  # Não era base64 — segue com os bytes originais

        logger.info(
            "Certificado carregado empresa=%s filial=%s tamanho=%d bytes",
            getattr(self.filial, 'empr_empr', '?'),
            getattr(self.filial, 'empr_codi', '?'),
            len(pfx_bytes),
        )

        from Licencas.crypto import decrypt_str
        senha = decrypt_str(self.filial.empr_senh_cert)

        return pfx_bytes, senha

    # =====================================================================
    # URL SEFAZ
    # =====================================================================
    def _resolve_url(self):
        uf = self.filial.empr_esta or "PR"
        key = "autorizacao_producao" if self.ambiente == 1 else "autorizacao_homologacao"

        if uf not in URLS_SEFAZ:
            raise ErroEmissao(f"UF {uf} sem Webservice configurado")

        return URLS_SEFAZ[uf][key]

    # =====================================================================
    # VERIFY TLS
    # =====================================================================
    def _resolve_verify(self):
        bundle = os.getenv("SEFAZ_CA_BUNDLE")
        if bundle and os.path.isfile(bundle):
            return bundle

        verify_env = os.getenv("SEFAZ_VERIFY", "").strip().lower()
        if verify_env in {"false", "0", "off", "no"}:
            return False

        return True