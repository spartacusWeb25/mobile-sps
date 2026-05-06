# transportes/services/emissao_service.py

import logging
import time
from decimal import Decimal

from transportes.models import Cte
from transportes.services.validacao_service import ValidacaoService
from transportes.services.numeracao_service import NumeracaoService
from transportes.services.fiscal_cte_service import FiscalCTeService
from transportes.builders.cte_xml_builder import CteXmlBuilder
from transportes.services.assinatura_service import AssinaturaService
from transportes.services.sefaz_gateway import SefazGateway
from Licencas.models import Filiais
from Entidades.models import Entidades

logger = logging.getLogger(__name__)


class EmissaoService:
    def __init__(self, cte: Cte, slug=None):
        self.cte = cte
        self.slug = slug

        self.validador = ValidacaoService(cte)
        self.numerador = NumeracaoService(
            cte.empresa,
            cte.filial,
            cte.serie,
            slug=slug,
        )

        empresa_adapter, operacao_adapter = self._build_adapters()
        self.fiscal_cte = FiscalCTeService(
            cte=self.cte,
            slug=slug,
            empresa=empresa_adapter,
            operacao=operacao_adapter,
        )

        self.xml_builder = CteXmlBuilder(cte)
        self.assinador = AssinaturaService(cte)
        self.gateway = SefazGateway(cte)

    def _build_adapters(self):
        db_alias = self.slug or self.cte._state.db or "default"

        filial = Filiais.objects.using(db_alias).filter(
            empr_empr=self.cte.empresa,
            empr_codi=self.cte.filial,
        ).first()

        simples_nacional = str(getattr(filial, "empr_regi_trib", "") or "") == "1"

        remetente = None
        if self.cte.remetente:
            remetente = Entidades.objects.using(db_alias).filter(pk=self.cte.remetente).first()

        destinatario = None
        if self.cte.destinatario:
            destinatario = Entidades.objects.using(db_alias).filter(pk=self.cte.destinatario).first()

        CODIGO_UF_PARA_SIGLA = {
            "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
            "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
            "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
            "41": "PR", "42": "SC", "43": "RS",
            "50": "MS", "51": "MT", "52": "GO", "53": "DF",
        }

        def get_uf_from_ibge(ibge_code):
            if not ibge_code:
                return None
            s_code = str(ibge_code).strip()
            if len(s_code) < 2:
                return None
            return CODIGO_UF_PARA_SIGLA.get(s_code[:2])

        uf_origem = get_uf_from_ibge(getattr(self.cte, "cidade_coleta", None))
        uf_destino = get_uf_from_ibge(getattr(self.cte, "cidade_entrega", None))

        if not uf_origem and remetente:
            uf_origem = getattr(remetente, "enti_esta", None)

        if not uf_destino and destinatario:
            uf_destino = getattr(destinatario, "enti_esta", None)

        uf_origem = (uf_origem or "").strip() or None
        uf_destino = (uf_destino or "").strip() or None

        ie_dest = getattr(destinatario, "enti_insc_esta", None) if destinatario else None
        ie_dest_clean = (ie_dest or "").strip().upper()
        contribuinte = bool(ie_dest_clean and ie_dest_clean not in {"ISENTO", "ISENTA", "NONE"})

        class ServiceEmpresaAdapter:
            def __init__(self, simples, db_alias_value="default"):
                self.simples_nacional = simples
                self._state = type("State", (), {"db": db_alias_value})

        class ServiceOperacaoAdapter:
            def __init__(self, uf_orig, uf_dest, contrib):
                self.uf_origem = uf_orig
                self.uf_destino = uf_dest
                self.contribuinte = contrib

        return ServiceEmpresaAdapter(simples_nacional, db_alias), ServiceOperacaoAdapter(uf_origem, uf_destino, contribuinte)

    def emitir(self):
        db_alias = self.slug or self.cte._state.db or "default"

        # 1. Validar
        if not self.validador.validar_emissao():
            raise Exception(
                "Falha na validação do CT-e: "
                + str(self.validador.get_errors())
            )

        # 2. Gerar número
        if not self.cte.numero:
            self.cte.numero = self.numerador.proximo_numero()
            self.cte.save(using=db_alias)

        # 3. Aplicar fiscal ANTES do XML
        try:
            self.fiscal_cte.aplicar()
        except Exception as e:
            raise Exception(f"Erro ao calcular tributação do CT-e: {str(e)}")

        # 4. Gerar XML já com campos fiscais salvos no CT-e
        try:
            xml_conteudo = self.xml_builder.build()
            self.cte.xml_cte = xml_conteudo
            self.cte.save(using=db_alias)
        except Exception as e:
            raise Exception(f"Erro ao gerar XML: {str(e)}")

        # 5. Assinar XML
        try:
            xml_assinado = self.assinador.assinar(xml_conteudo)
            self.cte.xml_cte = xml_assinado
            self.cte.save(using=db_alias)
        except Exception as e:
            raise Exception(f"Erro ao assinar XML: {str(e)}")

        # 6. Enviar para SEFAZ
        try:
            resultado_envio = self.gateway.enviar(xml_assinado)
        except Exception as e:
            raise Exception(f"Erro ao enviar para SEFAZ: {str(e)}")

        # 7. Atualizar status
        self._processar_retorno_envio(resultado_envio, db_alias)

        return resultado_envio

    def _processar_retorno_envio(self, resultado_envio, db_alias):
        status_envio = resultado_envio.get("status")
        mensagem_envio = resultado_envio.get("mensagem") or ""

        if mensagem_envio:
            self.cte.observacoes_fiscais = mensagem_envio

        if status_envio == "autorizado":
            self._processar_autorizacao(resultado_envio)
            return

        if status_envio == "recebido":
            self.cte.status = "REC"

            if resultado_envio.get("recibo"):
                self.cte.recibo = resultado_envio.get("recibo")

            self.cte.save(using=db_alias)
            self._consultar_recibo_se_necessario(resultado_envio, db_alias)
            return

        if status_envio == "processando":
            self.cte.status = "PRO"
            self.cte.save(using=db_alias)
            return

        if status_envio == "rejeitado":
            self.cte.status = "REJ"
            self.cte.save(using=db_alias)
            return

        self.cte.status = "ERR"
        self.cte.save(using=db_alias)

    def _consultar_recibo_se_necessario(self, resultado_envio, db_alias):
        recibo = self.cte.recibo

        if not recibo:
            return

        for tentativa in range(5):
            time.sleep(2)

            try:
                logger.info(
                    f"Consultando recibo {recibo} "
                    f"(tentativa {tentativa + 1}/5)..."
                )

                try:
                    retorno = self.gateway.consultar_recibo(recibo)
                except Exception:
                    chave = (getattr(self.cte, "chave_de_acesso", None) or "").strip()

                    if not chave:
                        raise

                    retorno = self.gateway.consultar_chave(chave)

                status = retorno.get("status")
                mensagem = retorno.get("mensagem") or ""

                if mensagem:
                    self.cte.observacoes_fiscais = mensagem

                if retorno.get("recibo"):
                    self.cte.recibo = retorno.get("recibo")

                if status == "autorizado":
                    self._processar_autorizacao(retorno)
                    resultado_envio.update(retorno)
                    break

                if status == "rejeitado":
                    self.cte.status = "REJ"
                    self.cte.save(using=db_alias)
                    resultado_envio.update(retorno)
                    break

                if status == "processando":
                    self.cte.status = "PRO"
                    self.cte.save(using=db_alias)
                    continue

                if status == "recebido":
                    self.cte.status = "REC"
                    self.cte.save(using=db_alias)
                    continue

                logger.warning(f"Status desconhecido na consulta: {status}")
                self.cte.save(using=db_alias)

            except Exception as e:
                logger.error(f"Erro ao consultar recibo {recibo}: {e}")
                continue

    def _processar_autorizacao(self, resultado):
        db_alias = self.slug or self.cte._state.db or "default"

        self.cte.status = "AUT"
        self.cte.protocolo = resultado.get("protocolo")

        xml_protocolo = resultado.get("xml_protocolo")

        if xml_protocolo and self.cte.xml_cte:
            xml_assinado_str = self.cte.xml_cte.strip()

            if xml_assinado_str.startswith("<?xml"):
                idx = xml_assinado_str.find(">")
                if idx != -1:
                    xml_assinado_str = xml_assinado_str[idx + 1:].strip()

            if not xml_assinado_str.startswith("<cteProc"):
                self.cte.xml_cte = (
                    '<cteProc xmlns="http://www.portalfiscal.inf.br/cte" '
                    'versao="4.00">'
                    f"{xml_assinado_str}"
                    f"{xml_protocolo}"
                    "</cteProc>"
                )

        self.cte.save(using=db_alias)
