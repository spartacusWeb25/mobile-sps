from decimal import Decimal
from django.db import transaction

from Pisos.models import Orcamentopisos, Itensorcapisos
from Pisos.services.utils_service import parse_decimal, arredondar
from Pisos.services.cliente_service import ClienteEnderecoService
from Pisos.services.credito_troca_service import CreditoTrocaPisosService
from Produtos.models import Produtos


class OrcamentoCriarService:
    @staticmethod
    def normalizar_erro(exc):
        """Normaliza exceções para mensagens amigáveis ao usuário."""
        if isinstance(exc, ValueError):
            return str(exc)
        if "duplicate key" in str(exc).lower():
            return "Já existe um orçamento com este número para esta empresa/filial."
        if "unique constraint" in str(exc).lower():
            return "Violação de restrição única: registro já existe."
        return str(exc)
    
    def _validar_campos_obrigatorios(self, dados):
        """Valida campos obrigatórios e retorna lista de campos faltantes."""
        campos_faltantes = []
        
        if not dados.get("orca_empr"):
            campos_faltantes.append("Empresa")
        if not dados.get("orca_fili"):
            campos_faltantes.append("Filial")
        
        return campos_faltantes
    
    def executar(self, *, banco, dados, itens):
        if not itens:
            raise ValueError("Itens do orçamento são obrigatórios.")
        
        campos_faltantes = self._validar_campos_obrigatorios(dados)
        if campos_faltantes:
            raise ValueError(f"Campos obrigatórios faltando: {', '.join(campos_faltantes)}")

        with transaction.atomic(using=banco):
            parametros = (dados or {}).get("parametros") or {}
            orcamento = self._criar_orcamento(
                banco=banco,
                dados=dados,
            )

            total = self._criar_itens(
                banco=banco,
                orcamento=orcamento,
                itens=itens,
            )

            desconto = parse_decimal(getattr(orcamento, "orca_desc", 0))
            frete = parse_decimal(getattr(orcamento, "orca_fret", 0))
            total_liquido_sem_credito = total - desconto + frete

            usar_credito = parametros.get("usar_credito")
            if usar_credito in (None, ""):
                usar_credito = parse_decimal(getattr(orcamento, "orca_cred", 0)) > 0

            credito_desejado = parametros.get("valor_credito")
            if credito_desejado in (None, ""):
                credito_desejado = getattr(orcamento, "orca_cred", None)

            credito_aplicado = Decimal("0.00")
            if usar_credito and getattr(orcamento, "orca_clie", None):
                credito_aplicado = CreditoTrocaPisosService.calcular_credito_aplicado(
                    banco=banco,
                    empresa=orcamento.orca_empr,
                    filial=orcamento.orca_fili,
                    cliente_id=orcamento.orca_clie,
                    total_liquido_sem_credito=total_liquido_sem_credito,
                    valor_desejado=credito_desejado,
                    excluir_orcamento=orcamento.orca_nume,
                )

            orcamento.orca_cred = credito_aplicado
            orcamento.orca_tota = arredondar(total_liquido_sem_credito - credito_aplicado)
            orcamento.save(using=banco, update_fields=["orca_tota", "orca_cred"])

            return orcamento

    def _criar_orcamento(self, *, banco, dados):
        ultimo = (
            Orcamentopisos.objects.using(banco)
            .filter(
                orca_empr=dados["orca_empr"],
                orca_fili=dados["orca_fili"],
            )
            .order_by("-orca_nume")
            .first()
        )

        # Normalize empresa/filial to ints to avoid mismatches
        try:
            dados_empr = int(dados.get("orca_empr"))
        except Exception:
            dados_empr = dados.get("orca_empr")
        try:
            dados_fili = int(dados.get("orca_fili"))
        except Exception:
            dados_fili = dados.get("orca_fili")

        proximo_numero = (ultimo.orca_nume + 1) if ultimo else 1

        dados_orcamento = dict(dados)
        dados_orcamento.pop("itens_input", None)
        dados_orcamento.pop("itens", None)
        dados_orcamento.pop("parametros", None)
        dados_orcamento.pop("usar_credito", None)
        dados_orcamento.pop("valor_credito", None)

        # Ensure orca_empr/orca_fili present in payload used to create the instance
        dados_orcamento["orca_empr"] = dados_empr
        dados_orcamento["orca_fili"] = dados_fili
        dados_orcamento["orca_tota"] = Decimal("0.00")

        # Encontrar próximo número livre (pular números já existentes)
        max_tentativas = 200
        tentativa = 0

        import logging
        logger = logging.getLogger(__name__)

        while tentativa < max_tentativas:
            tentativa += 1
            dados_orcamento["orca_nume"] = proximo_numero

            # Verificar se já existe
            existe = Orcamentopisos.objects.using(banco).filter(
                orca_empr=dados_empr,
                orca_fili=dados_fili,
                orca_nume=proximo_numero
            ).exists()

            if not existe:
                # Tentar salvar; pode haver condição de corrida -> capturar IntegrityError e tentar próximo número
                orcamento = Orcamentopisos(**dados_orcamento)
                try:
                    orcamento.save(using=banco, force_insert=True)
                    logger.info(f"Orçamento criado: empr={dados_empr} fili={dados_fili} num={proximo_numero}")
                    break
                except Exception as e:
                    # Se for violação de chave única, incrementa e tenta novamente
                    if 'duplicate key' in str(e).lower() or 'unique constraint' in str(e).lower():
                        logger.warning(f"Número {proximo_numero} já foi ocupado, tentando próximo. Erro: {e}")
                        proximo_numero += 1
                        continue
                    # Caso contrário, relança
                    raise
            else:
                proximo_numero += 1

        if tentativa >= max_tentativas:
            raise ValueError("Não foi possível encontrar um número disponível para o orçamento após várias tentativas.")

        ClienteEnderecoService.preencher_orcamento(
            banco=banco,
            orcamento=orcamento,
        )

        return orcamento

    def _criar_itens(self, *, banco, orcamento, itens):
        total = Decimal("0.00")
        campos_permitidos = {field.name for field in Itensorcapisos._meta.fields}

        for idx, item in enumerate(itens, start=1):
            dados_item = self._normalizar_item(item, banco=banco, empresa=orcamento.orca_empr)

            dados_item = {
                chave: valor
                for chave, valor in dados_item.items()
                if chave in campos_permitidos
            }

            quantidade = parse_decimal(dados_item.get("item_quan"))
            valor_unitario = parse_decimal(dados_item.get("item_unit"))
            subtotal = arredondar(quantidade * valor_unitario)

            extra_kwargs = {}
            if 'item_kg' in campos_permitidos:
                extra_kwargs['item_kg'] = parse_decimal(dados_item.get("item_kg") or dados_item.get("kg_total") or dados_item.get("quilos_total"))

            Itensorcapisos.objects.using(banco).create(
                item_empr=orcamento.orca_empr,
                item_fili=orcamento.orca_fili,
                item_orca=orcamento.orca_nume,
                item_nume=idx,
                item_ambi=dados_item.get("item_ambi") or 1,
                item_suto=subtotal,
                **extra_kwargs,
                **{
                    chave: valor
                    for chave, valor in dados_item.items()
                    if chave not in {
                        "item_empr",
                        "item_fili",
                        "item_orca",
                        "item_nume",
                        "item_ambi",
                        "item_suto",
                    }
                },
            )

            total += subtotal

        return total

    def _normalizar_item(self, item, *, banco, empresa):
        dados = dict(item)

        mapa = {
            "area_m2": "item_m2",
            "observacoes": "item_obse",
            "quebra": "item_queb",
            "item_nome": "item_nome_ambi",
        }

        for origem, destino in mapa.items():
            if origem in dados:
                dados[destino] = dados.pop(origem)

        dados.pop("produto_nome", None)

        dados_calc = dados.pop("dados_calculo", None) or {}

        if dados_calc:
            if not dados.get("item_caix"):
                dados["item_caix"] = dados_calc.get("caixas_necessarias")

            if not dados.get("item_quan"):
                caixas = parse_decimal(dados.get("item_caix"))
                pc_por_caixa = parse_decimal(dados_calc.get("pc_por_caixa"))
                m2_por_caixa = parse_decimal(dados_calc.get("m2_por_caixa"))

                if pc_por_caixa > 0:
                    dados["item_quan"] = pc_por_caixa * caixas
                elif m2_por_caixa > 0:
                    dados["item_quan"] = m2_por_caixa * caixas

        if not dados.get("item_ambi"):
            dados["item_ambi"] = 1

        if not dados.get("item_nome_ambi"):
            dados["item_nome_ambi"] = "Padrão"

        self._completar_medidas_item(dados, banco=banco, empresa=empresa)

        dados["item_m2"] = parse_decimal(dados.get("item_m2"))
        dados["item_quan"] = parse_decimal(dados.get("item_quan"))
        dados["item_unit"] = parse_decimal(dados.get("item_unit"))
        dados["item_desc"] = parse_decimal(dados.get("item_desc"))
        dados["item_queb"] = parse_decimal(dados.get("item_queb"))

        return dados

    def _completar_medidas_item(self, dados: dict, *, banco, empresa) -> None:
        produto_id = (dados.get("item_prod") or "").strip()
        if not produto_id:
            return

        quantidade = parse_decimal(dados.get("item_quan"))
        caixas = parse_decimal(dados.get("item_caix"))
        metragem = parse_decimal(dados.get("item_m2"))

        if quantidade > 0 and caixas > 0 and metragem > 0:
            return

        produto = Produtos.objects.using(banco).filter(prod_codi=produto_id, prod_empr=str(empresa)).first()
        if not produto:
            return

        m2_por_caixa = parse_decimal(getattr(produto, "prod_cera_m2cx", 0))
        pc_por_caixa = parse_decimal(getattr(produto, "prod_cera_pccx", 0))

        if caixas <= 0 and quantidade > 0 and pc_por_caixa > 0:
            caixas = quantidade / pc_por_caixa

        if quantidade <= 0 and caixas > 0:
            if pc_por_caixa > 0:
                quantidade = caixas * pc_por_caixa
            elif m2_por_caixa > 0:
                quantidade = caixas * m2_por_caixa

        if metragem <= 0:
            if caixas > 0 and m2_por_caixa > 0:
                metragem = caixas * m2_por_caixa
            elif quantidade > 0 and pc_por_caixa > 0 and m2_por_caixa > 0:
                metragem = (quantidade / pc_por_caixa) * m2_por_caixa

        dados["item_caix"] = caixas
        dados["item_quan"] = quantidade
        dados["item_m2"] = metragem
