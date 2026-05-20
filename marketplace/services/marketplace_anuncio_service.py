from django.db import transaction

from marketplace.models import MarketplaceProduto, MarketplaceAnuncio
from Produtos.models import Produtos, Tabelaprecos, SaldoProduto

from .mercado_livre_api_service import MercadoLivreApiService
from .mercado_livre_categoria_service import MercadoLivreCategoriaService


class MarketplaceAnuncioService:
    def __init__(self, db_alias="default"):
        self.db_alias = db_alias

    def _buscar_produto(self, empresa, produto_codigo):
        return Produtos.objects.using(self.db_alias).get(
            prod_empr=str(empresa),
            prod_codi=produto_codigo,
        )

    def _buscar_preco(self, empresa, filial, produto_codigo):
        tabela = Tabelaprecos.objects.using(self.db_alias).filter(
            tabe_empr=empresa,
            tabe_fili=filial,
            tabe_prod=produto_codigo,
        ).first()

        if not tabela:
            return None

        return tabela.tabe_prco or tabela.tabe_avis or tabela.tabe_apra

    def _buscar_estoque(self, empresa, filial, produto_codigo):
        saldo = SaldoProduto.objects.using(self.db_alias).filter(
            empresa=str(empresa),
            filial=str(filial),
            produto_codigo_id=produto_codigo,
        ).first()

        if not saldo:
            return 0

        return saldo.saldo_estoque or 0

    def _montar_atributos_basicos(self, produto):
        atributos = []

        if getattr(produto, "prod_gtin", None) and produto.prod_gtin != "SEM GTIN":
            atributos.append({
                "id": "GTIN",
                "value_name": produto.prod_gtin,
            })

        if getattr(produto, "prod_marc", None):
            atributos.append({
                "id": "BRAND",
                "value_name": str(produto.prod_marc),
            })

        if getattr(produto, "prod_codi", None):
            atributos.append({
                "id": "MODEL",
                "value_name": produto.prod_codi,
            })

        return atributos

    def _montar_payload(self, produto, integracao, preco, estoque, categoria_id, atributos_obrigatorios=None):
        atributos = self._montar_atributos_basicos(produto)

        obrigatorios = atributos_obrigatorios or []
        existentes = {a.get("id") for a in atributos}

        def _escolher_valor_from_values(values, preferencias=None):
            if not values:
                return None
            prefs = [str(p).strip().lower() for p in (preferencias or []) if p]
            for pref in prefs:
                for v in values:
                    name = (v.get("name") or v.get("value_name") or "")
                    if str(name).strip().lower() == pref:
                        return v
            return values[0]

        for attr in obrigatorios:
            aid = attr.get("id")
            if not aid or aid in existentes:
                continue

            value_id = None
            value_name = None

            if aid == "GTIN":
                if getattr(produto, "prod_gtin", None) and produto.prod_gtin != "SEM GTIN":
                    value_name = produto.prod_gtin
            elif aid == "BRAND":
                if getattr(produto, "prod_marc", None):
                    candidato = _escolher_valor_from_values(attr.get("values", []), [str(produto.prod_marc)])
                    if candidato and candidato.get("id"):
                        value_id = candidato.get("id")
                    else:
                        value_name = str(produto.prod_marc)
            elif aid in ("MODEL", "SELLER_SKU"):
                if getattr(produto, "prod_codi", None):
                    value_name = produto.prod_codi
            elif aid in ("EAN", "BARCODE"):
                if getattr(produto, "prod_coba", None):
                    value_name = getattr(produto, "prod_coba", None)
            elif aid == "NCM":
                if getattr(produto, "prod_ncm", None):
                    value_name = getattr(produto, "prod_ncm", None)
            else:
                candidato = _escolher_valor_from_values(attr.get("values", []), [getattr(produto, "prod_marc", ""), getattr(produto, "prod_nome", "")])
                if candidato:
                    if candidato.get("id"):
                        value_id = candidato.get("id")
                    else:
                        value_name = candidato.get("name") or candidato.get("value_name")

            if value_id:
                atributos.append({"id": aid, "value_id": value_id})
                existentes.add(aid)
            elif value_name:
                atributos.append({"id": aid, "value_name": value_name})
                existentes.add(aid)
            else:
                vals = attr.get("values") or []
                if vals:
                    v = vals[0]
                    if v.get("id"):
                        atributos.append({"id": aid, "value_id": v.get("id")})
                    elif v.get("name"):
                        atributos.append({"id": aid, "value_name": v.get("name")})
                    existentes.add(aid)

        payload = {
            "title": (produto.prod_nome or "")[:60],
            "category_id": categoria_id,
            "seller_custom_field": integracao.mark_sku_codi,
            "price": float(preco or 0),
            "available_quantity": max(int(estoque or 0), 1),
            "currency_id": "BRL",
            "buying_mode": "buy_it_now",
            "condition": "new",
            "listing_type_id": "gold_special",
            "description": {"plain_text": (produto.prod_nome or "")[:50000]},
            "attributes": atributos,
            "shipping": {"mode": "not_specified"},
        }

        if getattr(produto, "prod_foto", None):
            try:
                payload["pictures"] = [{"source": f"/web/produtos/{produto.prod_codi}/foto/"}]
            except Exception:
                pass

        return payload

    def _montar_configs_padrao(self, produto, quantidade):
        configs = []

        for i in range(quantidade):
            sufixo = "" if i == 0 else f" #{i + 1}"

            configs.append({
                "titulo": f"{produto.prod_nome}{sufixo}",
                "tipo_anuncio": "gold_special",
                "preco": None,
                "estoque": None,
            })

        return configs

    @transaction.atomic
    def gerar_rascunhos(
        self,
        empresa,
        filial,
        marketplace_produto_id,
        quantidade=1,
        anuncios_config=None,
    ):
        integracao = MarketplaceProduto.objects.using(self.db_alias).get(
            id=marketplace_produto_id,
            mark_empr=empresa,
            mark_fili=filial,
        )

        produto = self._buscar_produto(
            empresa=empresa,
            produto_codigo=integracao.mark_prod_codi,
        )

        preco_base = self._buscar_preco(
            empresa=empresa,
            filial=filial,
            produto_codigo=integracao.mark_prod_codi,
        )

        estoque_base = self._buscar_estoque(
            empresa=empresa,
            filial=filial,
            produto_codigo=integracao.mark_prod_codi,
        )

        api = MercadoLivreApiService(
            db_alias=self.db_alias,
            empresa=empresa,
            filial=filial,
        )

        categoria_service = MercadoLivreCategoriaService(api_service=api)

        categoria_id = categoria_service.prever_categoria(produto.prod_nome)
        if not categoria_id:
            categoria_id = "MLB1953"

        atributos_obrigatorios = categoria_service.buscar_atributos_obrigatorios(
            categoria_id
        )

        configs = anuncios_config or self._montar_configs_padrao(
            produto=produto,
            quantidade=quantidade,
        )

        anuncios = []

        for config in configs:
            titulo = config.get("titulo") or produto.prod_nome
            tipo_anuncio = config.get("tipo_anuncio") or "gold_special"
            preco = config.get("preco")
            estoque = config.get("estoque")

            preco_final = preco if preco is not None else preco_base
            estoque_final = estoque if estoque is not None else estoque_base

            payload = self._montar_payload(
                produto=produto,
                integracao=integracao,
                preco=preco_final,
                estoque=estoque_final,
                categoria_id=categoria_id,
                atributos_obrigatorios=atributos_obrigatorios,
            )

            payload["title"] = titulo[:60]
            payload["listing_type_id"] = tipo_anuncio

            anuncio = MarketplaceAnuncio.objects.using(self.db_alias).create(
                maan_produto=integracao,
                maan_titu=titulo[:255],
                maan_cate_id=categoria_id,
                maan_tipo_anun=tipo_anuncio,
                maan_prec=preco_final,
                maan_esto=estoque_final,
                maan_stat="RASCUNHO",
                maan_payload_env=payload,
            )

            anuncios.append(anuncio)

        return anuncios

    def gerar_rascunho(self, empresa, filial, marketplace_produto_id):
        anuncios = self.gerar_rascunhos(
            empresa=empresa,
            filial=filial,
            marketplace_produto_id=marketplace_produto_id,
            quantidade=1,
        )

        return anuncios[0], True

    @transaction.atomic
    def publicar_rascunho(self, empresa, filial, anuncio_id):
        anuncio = MarketplaceAnuncio.objects.using(self.db_alias).select_related(
            "maan_produto"
        ).get(
            id=anuncio_id,
            maan_produto__mark_empr=empresa,
            maan_produto__mark_fili=filial,
        )

        if anuncio.maan_stat != "RASCUNHO":
            raise ValueError("Somente anúncios em RASCUNHO podem ser publicados.")

        if not anuncio.maan_payload_env:
            raise ValueError("Anúncio sem payload de envio.")

        api = MercadoLivreApiService(
            db_alias=self.db_alias,
            empresa=empresa,
            filial=filial,
        )

        payload = anuncio.maan_payload_env or {}

        try:
            categoria_service = MercadoLivreCategoriaService(api_service=api)

            needs_update = False

            if not payload.get("category_id"):
                try:
                    produto = self._buscar_produto(
                        empresa=empresa,
                        produto_codigo=anuncio.maan_produto.mark_prod_codi,
                    )
                    categoria_id = categoria_service.prever_categoria(produto.prod_nome)
                    if not categoria_id:
                        categoria_id = "MLB1953"
                    payload["category_id"] = categoria_id
                    anuncio.maan_cate_id = categoria_id
                    needs_update = True
                except Exception:
                    pass

            # garantir atributos obrigatórios (complementar atributos mesmo quando já existem)
            try:
                if payload.get("category_id"):
                    obrig = categoria_service.buscar_atributos_obrigatorios(payload.get("category_id"))
                    try:
                        produto = produto if 'produto' in locals() else self._buscar_produto(
                            empresa=empresa,
                            produto_codigo=anuncio.maan_produto.mark_prod_codi,
                        )
                    except Exception:
                        produto = None

                    existing_attrs = payload.get("attributes") or []
                    existentes = {a.get("id") for a in existing_attrs}

                    def _escolher_valor_from_values(values, preferencias=None):
                        if not values:
                            return None
                        prefs = [str(p).strip().lower() for p in (preferencias or []) if p]
                        for pref in prefs:
                            for v in values:
                                name = (v.get("name") or v.get("value_name") or "")
                                if str(name).strip().lower() == pref:
                                    return v
                        return values[0]

                    for attr in obrig:
                        aid = attr.get("id")
                        if not aid or aid in existentes:
                            continue

                        value_id = None
                        value_name = None

                        if aid == "GTIN" and produto and getattr(produto, "prod_gtin", None) and produto.prod_gtin != "SEM GTIN":
                            value_name = produto.prod_gtin
                        elif aid == "BRAND" and produto and getattr(produto, "prod_marc", None):
                            candidato = _escolher_valor_from_values(attr.get("values", []), [str(produto.prod_marc)])
                            if candidato and candidato.get("id"):
                                value_id = candidato.get("id")
                            else:
                                value_name = str(produto.prod_marc)
                        elif aid in ("MODEL", "SELLER_SKU") and produto and getattr(produto, "prod_codi", None):
                            value_name = produto.prod_codi
                        elif aid in ("EAN", "BARCODE") and produto and getattr(produto, "prod_coba", None):
                            value_name = getattr(produto, "prod_coba", None)
                        elif aid == "NCM" and produto and getattr(produto, "prod_ncm", None):
                            value_name = getattr(produto, "prod_ncm", None)
                        else:
                            candidato = _escolher_valor_from_values(attr.get("values", []), [getattr(produto, "prod_marc", ""), getattr(produto, "prod_nome", "")])
                            if candidato:
                                if candidato.get("id"):
                                    value_id = candidato.get("id")
                                else:
                                    value_name = candidato.get("name") or candidato.get("value_name")

                        if value_id:
                            existing_attrs.append({"id": aid, "value_id": value_id})
                            existentes.add(aid)
                            needs_update = True
                        elif value_name:
                            existing_attrs.append({"id": aid, "value_name": value_name})
                            existentes.add(aid)
                            needs_update = True
                        else:
                            vals = attr.get("values") or []
                            if vals:
                                v = vals[0]
                                if v.get("id"):
                                    existing_attrs.append({"id": aid, "value_id": v.get("id")})
                                elif v.get("name"):
                                    existing_attrs.append({"id": aid, "value_name": v.get("name")})
                                existentes.add(aid)
                                needs_update = True

                    if existing_attrs and existing_attrs != payload.get("attributes"):
                        payload["attributes"] = existing_attrs
                        needs_update = True
            except Exception:
                pass

            # tentar incluir pictures se ausentes
            if not payload.get("pictures"):
                try:
                    produto = produto if 'produto' in locals() else self._buscar_produto(
                        empresa=empresa,
                        produto_codigo=anuncio.maan_produto.mark_prod_codi,
                    )
                    if getattr(produto, "prod_foto", None):
                        payload["pictures"] = [{"source": f"/web/produtos/{produto.prod_codi}/foto/"}]
                        needs_update = True
                except Exception:
                    pass

            # garantir currency_id, price, title e available_quantity mínimos
            try:
                if not payload.get("currency_id"):
                    payload["currency_id"] = "BRL"
                    needs_update = True

                if not payload.get("price"):
                    payload["price"] = float(getattr(anuncio, "maan_prec", 0) or 0)
                    needs_update = True

                if not payload.get("title"):
                    payload["title"] = (getattr(anuncio, "maan_titu", None) or "").strip()[:60]
                    needs_update = True

                if not payload.get("description"):
                    payload["description"] = {"plain_text": (getattr(anuncio, "maan_titu", None) or "")[:50000]}
                    needs_update = True

                if not payload.get("available_quantity"):
                    payload["available_quantity"] = max(int(getattr(anuncio, "maan_esto", 0) or 0), 1)
                    needs_update = True

                if not payload.get("seller_custom_field"):
                    try:
                        sku = anuncio.maan_produto.mark_sku_codi
                        if sku:
                            payload["seller_custom_field"] = sku
                            needs_update = True
                    except Exception:
                        pass
            except Exception:
                pass

            if needs_update:
                anuncio.maan_payload_env = payload
                try:
                    anuncio.save(
                        using=self.db_alias,
                        update_fields=["maan_payload_env", "maan_cate_id", "maan_atua_em"],
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # Normalizar e validar campos essenciais antes do envio
        try:
            payload["currency_id"] = (payload.get("currency_id") or "BRL")
            if isinstance(payload["currency_id"], str):
                payload["currency_id"] = payload["currency_id"].upper()
            else:
                payload["currency_id"] = "BRL"

            price = payload.get("price")
            try:
                price = float(price) if price is not None else float(getattr(anuncio, "maan_prec", 0) or 0)
            except Exception:
                price = float(getattr(anuncio, "maan_prec", 0) or 0)

            if price <= 0:
                raise ValueError("Preço inválido para publicação no Mercado Livre.")

            payload["price"] = price

            if not payload.get("seller_custom_field"):
                try:
                    payload["seller_custom_field"] = anuncio.maan_produto.mark_sku_codi
                except Exception:
                    payload["seller_custom_field"] = payload.get("seller_custom_field") or None

        except Exception as e:
            try:
                anuncio.maan_payload_ret = {"error": str(e)}
                anuncio.maan_stat = "ERRO"
                anuncio.save(using=self.db_alias, update_fields=["maan_payload_ret", "maan_stat", "maan_atua_em"])
            except Exception:
                pass
            raise

        try:
            logger = __import__('logging').getLogger(__name__)
            logger.debug(f"Publicando anúncio ML payload: {payload}")
        except Exception:
            pass

        try:
            retorno = api.publicar_anuncio(payload)
        except Exception as e:
            try:
                anuncio.maan_payload_ret = {"error": str(e)}
                anuncio.maan_stat = "ERRO"
                anuncio.save(using=self.db_alias, update_fields=["maan_payload_ret", "maan_stat", "maan_atua_em"])
            except Exception:
                pass

            try:
                integracao = anuncio.maan_produto
                integracao.mark_stat = "ERRO"
                integracao.mark_ulti_erro = str(e)
                integracao.save(using=self.db_alias, update_fields=["mark_stat", "mark_ulti_erro", "mark_atua_em"])
            except Exception:
                pass

            raise

        anuncio.maan_item_id = retorno.get("id")
        anuncio.maan_url = retorno.get("permalink")
        anuncio.maan_payload_ret = retorno
        anuncio.maan_stat = "PUBLICADO"

        anuncio.save(
            using=self.db_alias,
            update_fields=[
                "maan_item_id",
                "maan_url",
                "maan_payload_ret",
                "maan_stat",
                "maan_atua_em",
            ],
        )

        integracao = anuncio.maan_produto
        integracao.mark_stat = "INTEGRADO"
        integracao.mark_ulti_erro = None
        integracao.save(
            using=self.db_alias,
            update_fields=[
                "mark_stat",
                "mark_ulti_erro",
                "mark_atua_em",
            ],
        )

        return anuncio

    def publicar_rascunhos(self, empresa, filial, marketplace_produto_id=None, anuncio_ids=None):
        """Publica vários rascunhos. Retorna um dict com resumo: {"success": [], "failed": [{"id":..., "error":...}], "skipped": []}

        Você pode passar anuncio_ids (lista de ids) ou marketplace_produto_id (publica todos os rascunhos daquele produto).
        """
        resultados = {"success": [], "failed": [], "skipped": []}

        if anuncio_ids is None and marketplace_produto_id is None:
            raise ValueError("Forneça anuncio_ids ou marketplace_produto_id")

        if anuncio_ids is not None:
            qs = MarketplaceAnuncio.objects.using(self.db_alias).filter(
                id__in=list(anuncio_ids),
                maan_produto__mark_empr=empresa,
                maan_produto__mark_fili=filial,
            )
        else:
            qs = MarketplaceAnuncio.objects.using(self.db_alias).filter(
                maan_produto_id=marketplace_produto_id,
                maan_produto__mark_empr=empresa,
                maan_produto__mark_fili=filial,
            )

        for a in qs.order_by("id"):
            if a.maan_stat != "RASCUNHO":
                resultados["skipped"].append(a.id)
                continue
            try:
                publicado = self.publicar_rascunho(empresa=empresa, filial=filial, anuncio_id=a.id)
                resultados["success"].append(a.id)
            except Exception as e:
                resultados["failed"].append({"id": a.id, "error": str(e)})
                # continue com os próximos
                continue

        return resultados
