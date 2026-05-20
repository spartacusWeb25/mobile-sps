import requests
from django.conf import settings
from .auth import get_access_token
from ..models_integra import ContaMercadoLivre
from ..models import ProdutoImagem
import json
import os
from datetime import datetime, timedelta
from django.core.cache import cache

class MercadoLivreService:
    BASE_URL = 'https://api.mercadolibre.com'

    def __init__(self, empresa, filial, slug=None):
        self.empresa = empresa
        self.filial = filial
        self.slug = slug
        self.token = get_access_token(empresa, filial)
    
    def _get_category_prediction(self, titulo):
        """Usa o preditor de categorias do ML para encontrar a melhor categoria"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            url = f"{self.BASE_URL}/sites/MLB/domain_discovery/search"
            params = {
                'q': titulo[:100],  # Limitar título para evitar erros
                'limit': 1
            }
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0].get('category_id')
        except Exception as e:
            print(f"Erro ao obter predição de categoria: {e}")
        
        # Fallback para categoria genérica válida
        return "MLB1953"  # "Mais Categorias" - categoria folha válida
    
    def _check_category_attributes(self, category_id):
        """Verifica se a categoria exige GTIN e outros atributos obrigatórios"""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(f"{self.BASE_URL}/categories/{category_id}/attributes", headers=headers)
            
            if response.status_code == 200:
                attributes = response.json()
                required_attrs = {}
                
                for attr in attributes:
                    attr_id = attr.get('id')
                    tags = attr.get('tags', {})
                    
                    # Verificar se é obrigatório ou condicionalmente obrigatório
                    if tags.get('required') or tags.get('conditional_required'):
                        required_attrs[attr_id] = {
                            'required': tags.get('required', False),
                            'conditional_required': tags.get('conditional_required', False),
                            'values': attr.get('values', []),
                            'value_type': attr.get('value_type')
                        }
                
                return required_attrs
        except Exception as e:
            print(f"Erro ao verificar atributos da categoria {category_id}: {e}")
        
        return {}
    
    def _get_category_without_gtin(self, titulo, categoria_marketplace=None):
        """Encontra uma categoria que não exige GTIN nem SIZE_GRID_ID"""
        # Primeiro tenta encontrar a melhor categoria
        category_id = self._get_best_category_for_product(titulo, categoria_marketplace)
        
        # Verifica se a categoria exige GTIN ou SIZE_GRID_ID
        required_attrs = self._check_category_attributes(category_id)
        exige_gtin = False
        exige_size_grid = False
        
        if 'GTIN' in required_attrs:
            gtin_attr = required_attrs['GTIN']
            exige_gtin = gtin_attr.get('required') or gtin_attr.get('conditional_required')
            
        if 'SIZE_GRID_ID' in required_attrs:
            size_grid_attr = required_attrs['SIZE_GRID_ID']
            exige_size_grid = size_grid_attr.get('required') or size_grid_attr.get('conditional_required')
        
        if not exige_gtin and not exige_size_grid:
            return category_id
        
        # Se exige GTIN ou SIZE_GRID_ID, busca alternativas
        problemas = []
        if exige_gtin:
            problemas.append("GTIN")
        if exige_size_grid:
            problemas.append("SIZE_GRID_ID")
        print(f"Categoria {category_id} exige {', '.join(problemas)}. Buscando alternativas...")
        
        # Busca por categorias que tipicamente não exigem GTIN nem SIZE_GRID_ID
        alternative_terms = ['UTENSÍLIOS', 'DECORAÇÃO', 'CASA', 'OBJETOS DECORATIVOS']
        alternatives = self._find_leaf_categories(alternative_terms)
        
        for alt in alternatives:
            alt_attrs = self._check_category_attributes(alt['id'])
            alt_exige_gtin = False
            alt_exige_size_grid = False
            
            if 'GTIN' in alt_attrs:
                gtin_attr = alt_attrs['GTIN']
                alt_exige_gtin = gtin_attr.get('required') or gtin_attr.get('conditional_required')
                
            if 'SIZE_GRID_ID' in alt_attrs:
                size_grid_attr = alt_attrs['SIZE_GRID_ID']
                alt_exige_size_grid = size_grid_attr.get('required') or size_grid_attr.get('conditional_required')
            
            if not alt_exige_gtin and not alt_exige_size_grid:
                print(f"Alternativa encontrada: {alt['id']} - {alt['name']}")
                return alt['id']
        
        # Fallback para categorias conhecidas que não exigem GTIN nem SIZE_GRID_ID
        safe_categories = [
            "MLB1574",  # Casa, Móveis e Decoração
            "MLB1953",  # Mais Categorias
            "MLB1499"   # Indústria e Comércio
        ]
        
        for safe_cat in safe_categories:
            safe_attrs = self._check_category_attributes(safe_cat)
            safe_exige_gtin = False
            safe_exige_size_grid = False
            
            if 'GTIN' in safe_attrs:
                gtin_attr = safe_attrs['GTIN']
                safe_exige_gtin = gtin_attr.get('required') or gtin_attr.get('conditional_required')
                
            if 'SIZE_GRID_ID' in safe_attrs:
                size_grid_attr = safe_attrs['SIZE_GRID_ID']
                safe_exige_size_grid = size_grid_attr.get('required') or size_grid_attr.get('conditional_required')
            
            if not safe_exige_gtin and not safe_exige_size_grid:
                print(f"Categoria segura encontrada: {safe_cat}")
                return safe_cat
        
        # Fallback final - usar categoria mais genérica possível
        print("Usando categoria fallback final mais genérica.")
        return "MLB1574"  # Casa, Móveis e Decoração - categoria mais genérica


    
    def publicar_produto_com_categoria(self, produto, category_id_escolhida):
        """Publica produto usando uma categoria específica escolhida pelo usuário"""
        pictures = [
            {"source": img.url_imagem}
            for img in ProdutoImagem.objects.filter(produto_codigo=produto.produto_codigo, ativo=True).order_by("ordem")
            if img.url_imagem
        ]

        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")

        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")

        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")

        # Usar a categoria escolhida diretamente
        attributes = self._get_required_attributes_for_category(category_id_escolhida, titulo, produto_dados)

        # Determinar listing_type_id baseado na presença de imagens
        listing_type_id = "gold_special" if pictures else "bronze"
        
        payload = {
            "title": titulo[:60],
            "category_id": category_id_escolhida,
            "price": preco,
            "currency_id": "BRL",
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "buying_mode": "buy_it_now",
            "listing_type_id": listing_type_id,
            "condition": "new",
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            },
            "shipping": {
                "mode": "not_specified",
                "free_shipping": True
            },
            "attributes": attributes
        }

        # Adicionar imagens se disponíveis
        if pictures:
            payload["pictures"] = pictures[:10]
        else:
            # Para bronze sem imagens, usar imagem placeholder
            payload["pictures"] = [{
                "source": "https://via.placeholder.com/500x500/CCCCCC/FFFFFF?text=Produto"
            }]

        print(json.dumps(payload, indent=2, ensure_ascii=False))

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.BASE_URL}/items", json=payload, headers=headers)

        if response.status_code != 201:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                details = [
                    f"{cause.get('code', 'campo_desconhecido')}: {cause.get('message', 'erro não especificado')}"
                    for cause in error_data.get('cause', [])
                ]
                raise Exception(f"Erro na API do ML: {error_message}. Detalhes: {'; '.join(details) or error_data}")
            except ValueError:
                raise Exception(f"Erro na API do ML (Status {response.status_code}): {response.text}")

        return response.json()
    
    def _get_required_attributes_for_category(self, category_id, titulo, produto_dados):
        """Obtém atributos obrigatórios para uma categoria específica"""
        # Usar a função padronizada
        return self._get_required_attributes(category_id, titulo, produto_dados)


    def publicar_produto(self, produto):
        """Publica um produto no Mercado Livre com validação e fallback inteligente"""

        pictures = [
            {"source": img.url_imagem}
            for img in ProdutoImagem.objects.filter(produto_codigo=produto.produto_codigo, ativo=True).order_by("ordem")
            if img.url_imagem
        ]

        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")

        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")

        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")

        # Usar mapeamento interno de categorias
        category_id = self._get_category_without_gtin(titulo, produto.categoria_marketplace)
        attributes = self._get_required_attributes(category_id, titulo, produto_dados)

        # Determinar listing_type_id baseado na presença de imagens
        listing_type_id = "gold_special" if pictures else "bronze"

        payload = {
            "title": titulo[:60],
            "category_id": category_id,
            "price": preco,
            "currency_id": "BRL",
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "buying_mode": "buy_it_now",
            "listing_type_id": listing_type_id,
            "condition": "new",
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            },
            "shipping": {
                "mode": "me2",
                "free_shipping": True
            },
            "attributes": attributes
        }

        # Adicionar imagens se disponíveis
        if pictures:
            payload["pictures"] = pictures[:10]
        else:
            # Para bronze sem imagens, usar imagem placeholder
            payload["pictures"] = [{
                "source": "https://via.placeholder.com/500x500/CCCCCC/FFFFFF?text=Produto"
            }]

        print(json.dumps(payload, indent=2, ensure_ascii=False))

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.BASE_URL}/items", json=payload, headers=headers)

        if response.status_code != 201:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                details = [
                    f"{cause.get('code', 'campo_desconhecido')}: {cause.get('message', 'erro não especificado')}"
                    for cause in error_data.get('cause', [])
                ]
                raise Exception(f"Erro na API do ML: {error_message}. Detalhes: {'; '.join(details) or error_data}")
            except ValueError:
                raise Exception(f"Erro na API do ML (Status {response.status_code}): {response.text}")

        return response.json()

    def atualizar_produto(self, item_id, produto):
        """Atualiza um produto já publicado no Mercado Livre"""
        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")
            
        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")
            
        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")
            
        payload = {
            "title": titulo[:60],
            "price": preco,
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            }
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                error_details = []
                
                if 'cause' in error_data:
                    for cause in error_data['cause']:
                        field = cause.get('code', 'campo_desconhecido')
                        message = cause.get('message', 'erro não especificado')
                        error_details.append(f"{field}: {message}")
                
                if error_details:
                    full_error = f"{error_message}. Detalhes: {'; '.join(error_details)}"
                else:
                    full_error = f"{error_message}. Response completo: {error_data}"
                    
                raise Exception(f"Erro ao atualizar no ML: {full_error}")
            except ValueError:
                raise Exception(f"Erro ao atualizar no ML (Status {response.status_code}): {response.text}")
            
        return response.json()
    
    def pausar_produto(self, item_id):
        """Pausa um produto no Mercado Livre"""
        payload = {"status": "paused"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def reativar_produto(self, item_id):
        """Reativa um produto pausado no Mercado Livre"""
        payload = {"status": "active"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def _get_cached_categories(self):
        """Obtém categorias do cache ou da API se necessário"""
        cache_key = 'ml_categories_all'
        categories = cache.get(cache_key)
        
        if not categories:
            print("Cache de categorias vazio. Baixando da API...")
            categories = self._fetch_all_categories()
            if categories:
                # Cache por 24 horas
                cache.set(cache_key, categories, 60 * 60 * 24)
                print(f"Cache atualizado com {len(categories)} categorias")
        else:
            print(f"Usando cache com {len(categories)} categorias")
        
        return categories or []
    
    def _fetch_all_categories(self):
        """Baixa todas as categorias da API do Mercado Livre (sem autenticação)"""
        try:
            # API pública não requer token
            response = requests.get(f"{self.BASE_URL}/sites/MLB/categories/all")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Erro ao buscar categorias: {response.status_code}")
                return None
        except Exception as e:
            print(f"Erro ao buscar categorias: {e}")
            return None
    
    def _find_leaf_categories(self, search_terms):
        """Encontra categorias folha baseadas em termos de busca"""
        categories = self._get_cached_categories()
        if not categories:
            return []
        
        leaf_categories = []
        search_terms_upper = [term.upper() for term in search_terms]
        
        def is_leaf_category(category):
            # Uma categoria é folha se não tem children_categories ou se está vazio
            children = category.get('children_categories', [])
            return not children or len(children) == 0
        
        def search_in_category(category, path=""):
            if not isinstance(category, dict):
                return
                
            current_path = f"{path} > {category.get('name', '')}" if path else category.get('name', '')
            
            # Se é folha, verifica se contém algum termo de busca
            if is_leaf_category(category):
                category_text = f"{category.get('name', '')} {category.get('id', '')} {current_path}".upper()
                for term in search_terms_upper:
                    if term in category_text:
                        leaf_categories.append({
                            'id': category.get('id', ''),
                            'name': category.get('name', ''),
                            'path': current_path,
                            'total_items': category.get('total_items_in_this_category', 0)
                        })
                        break
            
            # Busca recursivamente nos filhos
            children = category.get('children_categories', [])
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        search_in_category(child, current_path)
        
        # Busca em todas as categorias
        if isinstance(categories, dict):
            # Se categories é um dicionário com IDs como chaves
            for cat_id, category in categories.items():
                if isinstance(category, dict):
                    search_in_category(category)
        elif isinstance(categories, list):
            # Se categories é uma lista
            for category in categories:
                if isinstance(category, dict):
                    search_in_category(category)
        
        # Ordena por número de itens (mais populares primeiro)
        leaf_categories.sort(key=lambda x: x.get('total_items', 0), reverse=True)
        return leaf_categories
    
    def _get_best_category_for_product(self, titulo, categoria_marketplace=None):
        """Encontra a melhor categoria folha para o produto"""
        # Primeiro, tenta usar a predição da API do ML
        predicted_category = self._get_category_prediction(titulo)
        if predicted_category:
            # Verifica se a categoria predita é folha
            try:
                attrs = self._check_category_attributes(predicted_category)
                if attrs is not None:  # Categoria existe
                    print(f"Usando categoria predita pela API: {predicted_category}")
                    return predicted_category
            except:
                pass
        
        search_terms = []
        
        # Adiciona categoria do marketplace se fornecida
        if categoria_marketplace:
            search_terms.append(categoria_marketplace)
        
        # Extrai palavras-chave do título
        titulo_words = titulo.upper().split()
        keywords = ['PRATO', 'TALHER', 'FAQUEIRO', 'CRISTAL', 'CHUMBO', 'TAMPA', 
                   'PEARL', 'BOLEIRA', 'WOLFF', 'COZINHA', 'UTENSILIO', 'DECORACAO']
        
        for word in titulo_words:
            if any(keyword in word for keyword in keywords):
                search_terms.append(word)
        
        # Adiciona termos genéricos baseados no título
        if any(word in titulo.upper() for word in ['PRATO', 'BOLEIRA', 'TAMPA']):
            search_terms.extend(['PRATOS', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['TALHER', 'FAQUEIRO']):
            search_terms.extend(['TALHERES', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['CRISTAL', 'DECORACAO']):
            search_terms.extend(['DECORAÇÃO', 'OBJETOS DECORATIVOS', 'CASA'])
        
        if not search_terms:
            search_terms = ['UTENSÍLIOS', 'COZINHA', 'CASA']  # Fallback genérico
        
        print(f"Buscando categorias para: {search_terms}")
        
        # Busca categorias folha
        leaf_categories = self._find_leaf_categories(search_terms)
        
        if leaf_categories:
            best_category = leaf_categories[0]  # Primeira (mais popular)
            print(f"Categoria encontrada: {best_category['id']} - {best_category['name']} ({best_category['path']}) - {best_category['total_items']} itens")
            return best_category['id']
        
        # Fallback para categoria leaf conhecida e válida
        print("Nenhuma categoria específica encontrada. Usando categoria leaf segura como fallback.")
        return predicted_category or "MLB256842"  # Pratos - categoria leaf segura
    
    # ==========================
    # Pedidos (Orders) e Envios
    # ==========================
    def _get_seller_id(self):
        """Obtém e cacheia o seller_id (user id) da conta ML vinculada ao token."""
        cache_key = f"ml_seller_id_{self.empresa}_{self.filial}"
        seller_id = cache.get(cache_key)
        if seller_id:
            return seller_id
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(f"{self.BASE_URL}/users/me", headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Erro ao obter seller id: {resp.text}")
        seller_id = resp.json().get('id')
        if not seller_id:
            raise Exception("Resposta sem id do usuário ML")
        cache.set(cache_key, seller_id, 6 * 60 * 60)  # 6 horas
        return seller_id

    def listar_pedidos(self, date_from=None, statuses=None, limit=50, offset=0):
        """Lista pedidos do Mercado Livre do seller atual.

        - date_from: ISO8601 ou None (ex.: '2025-01-01T00:00:00.000-00:00')
        - statuses: lista de status do ML (ex.: ['paid','ready_to_ship'])
        """
        seller_id = self._get_seller_id()
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {
            'seller': seller_id,
            'limit': limit,
            'offset': offset,
            'sort': 'date_desc'
        }
        if date_from:
            params['order.date_created.from'] = date_from
        if statuses:
            params['order.status'] = ",".join(statuses)
        resp = requests.get(f"{self.BASE_URL}/orders/search", headers=headers, params=params)
        if resp.status_code != 200:
            raise Exception(f"Erro ao listar pedidos ML: {resp.text}")
        return resp.json()

    def obter_pedido(self, order_id):
        """Obtém detalhes de um pedido específico do ML."""
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(f"{self.BASE_URL}/orders/{order_id}", headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Erro ao obter pedido ML {order_id}: {resp.text}")
        return resp.json()

    def obter_envio_por_pedido(self, order):
        """Retorna detalhes do envio (shipment) associado a um pedido ML (dict)."""
        shipping = (order or {}).get('shipping') or {}
        shipment_id = shipping.get('id')
        if not shipment_id:
            return None
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.get(f"{self.BASE_URL}/shipments/{shipment_id}", headers=headers)
        if resp.status_code != 200:
            # Retorna informação bruta em caso de erro
            return {'error': True, 'detail': resp.text}
        return resp.json()

    def importar_pedidos_para_marketplace(self, date_from_iso=None, statuses=None):
        """Importa pedidos do ML para o modelo local PedidoMarketplace/ItemPedidoMarketplace.

        Observação: Sem alterações de schema, usamos session_key como chave externa 'ML:<order_id>'.
        """
        from ..models import PedidoMarketplace, ItemPedidoMarketplace
        import decimal
        resultados = {'importados': 0, 'atualizados': 0, 'erros': 0}
        data = self.listar_pedidos(date_from=date_from_iso, statuses=statuses or ['paid','ready_to_ship'])
        orders = data.get('results', [])
        for order in orders:
            try:
                ml_id = str(order.get('id'))
                session_key = f"ML:{ml_id}"
                buyer = order.get('buyer', {}) or {}
                shipping = order.get('shipping', {}) or {}
                total_amount = order.get('total_amount') or 0
                status = order.get('status') or 'pendente'
                # Mapear status ML para nosso status
                status_map = {
                    'confirmed': 'pendente',
                    'payment_required': 'pendente',
                    'paid': 'confirmado',
                    'fulfilled': 'enviado',
                    'cancelled': 'cancelado',
                }
                status_local = status_map.get(status, 'pendente')

                pedido, created = PedidoMarketplace.objects.get_or_create(
                    empresa_slug=self.slug or '',
                    session_key=session_key,
                    defaults={
                        'cliente_nome': (buyer.get('first_name','') + ' ' + buyer.get('last_name','')).strip() or buyer.get('nickname',''),
                        'cliente_email': buyer.get('email') or '',
                        'cliente_telefone': '',
                        'cliente_endereco': '',
                        'valor_total': decimal.Decimal(str(total_amount)),
                        'status': status_local,
                        'observacoes': f"Importado ML order_id={ml_id}"
                    }
                )

                if not created:
                    # Atualizar status/valor quando necessário
                    mudou = False
                    if pedido.status != status_local:
                        pedido.status = status_local
                        mudou = True
                    if pedido.valor_total != decimal.Decimal(str(total_amount)):
                        pedido.valor_total = decimal.Decimal(str(total_amount))
                        mudou = True
                    if mudou:
                        pedido.save()
                        resultados['atualizados'] += 1
                else:
                    # Inserir itens do pedido
                    order_items = order.get('order_items', []) or []
                    for idx, oi in enumerate(order_items, start=1):
                        item = oi.get('item') or {}
                        title = item.get('title') or ''
                        seller_sku = item.get('seller_sku') or item.get('id') or ''
                        quantity = oi.get('quantity') or 1
                        unit_price = oi.get('unit_price') or 0
                        ItemPedidoMarketplace.objects.create(
                            pedido=pedido,
                            produto_codigo=seller_sku or title or 'ML-ITEM',
                            produto_nome=title or seller_sku,
                            quantidade=int(quantity),
                            preco_unitario=decimal.Decimal(str(unit_price)),
                            subtotal=decimal.Decimal(str(unit_price)) * decimal.Decimal(str(quantity))
                        )
                    resultados['importados'] += 1
            except Exception:
                resultados['erros'] += 1
        return resultados

    def _get_category_attributes_from_api(self, category_id):
        """Busca atributos da categoria diretamente da API do Mercado Livre"""
        try:
            url = f"https://api.mercadolibre.com/categories/{category_id}/attributes"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Erro ao buscar atributos da categoria {category_id}: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Erro ao consultar atributos da categoria {category_id}: {str(e)}")
            return []
    
    def _extract_brand_from_title(self, titulo):
        """Extrai marca do título do produto"""
        titulo_upper = titulo.upper()
        
        # Marcas conhecidas
        marcas_conhecidas = {
            'WOLFF': 'Wolff',
            'ST.JAMES': 'St. James', 
            'FENDI': 'Fendi',
            'TRAMONTINA': 'Tramontina',
            'ZWILLING': 'Zwilling',
            'WMF': 'WMF',
            'OXFORD': 'Oxford',
            'BRINOX': 'Brinox'
        }
        
        for marca_key, marca_value in marcas_conhecidas.items():
            if marca_key in titulo_upper:
                return marca_value
        
        return "Genérica"
    
    def _extract_model_from_title(self, titulo):
        """Extrai modelo do título do produto"""
        import re
        
        # Tentar extrair modelo após marca ou palavras-chave
        model_patterns = [
            r'modelo\s+([\w\d\-\.]+)',
            r'mod\.?\s+([\w\d\-\.]+)',
            r'ref\.?\s+([\w\d\-\.]+)',
            r'([A-Z]{2,}\d+[A-Z]*)',  # Padrão alfanumérico
        ]
        
        for pattern in model_patterns:
            match = re.search(pattern, titulo, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Se não encontrou padrão específico, usar parte do título como modelo
        palavras = titulo.split()
        if len(palavras) >= 2:
            # Usar primeiras 2-3 palavras como modelo
            modelo = " ".join(palavras[:3]).replace(',', '').replace('.', '')
            return modelo[:50]  # Limitar tamanho
        elif len(palavras) == 1:
            return palavras[0][:50]
        
        return "Modelo Padrão"
    
    def _extract_color_from_title(self, titulo):
        """Extrai cor do título do produto"""
        titulo_lower = titulo.lower()
        
        cores_conhecidas = {
            'preto': '52049',
            'branco': '52055', 
            'prata': '52053',
            'dourado': '283164',
            'azul': '52028',
            'vermelho': '51993',
            'verde': '52014',
            'amarelo': '52007',
            'rosa': '51994',
            'roxo': '52035',
            'marrom': '52005',
            'cinza': '52051',
            'laranja': '52000'
        }
        
        for cor, value_id in cores_conhecidas.items():
            if cor in titulo_lower:
                return value_id
        
        return None
    
    def _extract_pieces_number(self, titulo):
        """Extrai número de peças do título"""
        import re
        
        # Padrões para extrair número de peças
        patterns = [
            r'(\d+)\s*pe[çc]as?',
            r'(\d+)\s*pcs?',
            r'(\d+)\s*itens?',
            r'conjunto\s+de\s+(\d+)',
            r'kit\s+com\s+(\d+)',
            r'jogo\s+de\s+(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, titulo, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Fallback baseado no tipo de produto
        titulo_upper = titulo.upper()
        if 'FAQUEIRO' in titulo_upper:
            # Para faqueiros, tentar extrair número do título
            num_match = re.search(r'(\d+)', titulo)
            return num_match.group(1) if num_match else "101"
        elif any(palavra in titulo_upper for palavra in ['JOGO', 'KIT', 'CONJUNTO']):
            return "6"  # Valor padrão para jogos/kits
        else:
            return "1"  # Peça única
    
    def _is_product_kit(self, titulo):
        """Verifica se o produto é um kit/conjunto"""
        kit_keywords = ['KIT', 'CONJUNTO', 'FAQUEIRO', 'JOGO', 'ESTOJO', 'PACK']
        return any(palavra in titulo.upper() for palavra in kit_keywords)
    
    def _find_default_list_value(self, attribute_values, default_names):
        """Encontra valor padrão em lista de valores de atributo"""
        if not attribute_values:
            return None
            
        for default_name in default_names:
            for value in attribute_values:
                if default_name.lower() in value.get('name', '').lower():
                    return value.get('id')
        
        # Se não encontrar, retornar o primeiro valor disponível
        return attribute_values[0].get('id') if attribute_values else None
    
    def _get_required_attributes(self, category_id, titulo, produto_dados):
        """Gera os atributos obrigatórios para a categoria do produto usando API do ML"""
        attributes = []
        
        # Buscar atributos da categoria via API
        category_attributes = self._get_category_attributes_from_api(category_id)
        
        if not category_attributes:
            logger.warning(f"Não foi possível obter atributos para categoria {category_id}")
            # Fallback para método antigo se API falhar
            return self._get_required_attributes_fallback(category_id, titulo, produto_dados)
        
        for attr in category_attributes:
            attr_id = attr.get('id')
            attr_tags = attr.get('tags', {})
            
            # Verificar se é obrigatório
            is_required = attr_tags.get('required', False) or attr_tags.get('conditional_required', False)
            
            if not is_required:
                continue
            
            # Processar atributos específicos
            if attr_id == 'GTIN' and is_required:
                # Adicionar EMPTY_GTIN_REASON quando GTIN for obrigatório
                attributes.append({
                    "id": "EMPTY_GTIN_REASON",
                    "value_id": "17055159"  # "Kit"
                })
            
            elif attr_id == 'BRAND':
                marca = self._extract_brand_from_title(titulo)
                if hasattr(produto_dados, 'marca') and produto_dados.marca:
                    marca = produto_dados.marca
                
                attributes.append({
                    "id": "BRAND",
                    "value_name": marca
                })
            
            elif attr_id == 'MODEL':
                modelo = self._extract_model_from_title(titulo)
                # Sempre adicionar MODEL se for obrigatório
                attributes.append({
                    "id": "MODEL",
                    "value_name": modelo
                })
            
            elif attr_id == 'COLOR':
                cor_id = self._extract_color_from_title(titulo)
                if cor_id:
                    attributes.append({
                        "id": "COLOR",
                        "value_id": cor_id
                    })
            
            elif attr_id == 'PIECES_NUMBER':
                num_pecas = self._extract_pieces_number(titulo)
                attributes.append({
                    "id": "PIECES_NUMBER",
                    "value_name": num_pecas
                })
            
            elif attr_id == 'IS_FACTORY_KIT':
                is_kit = self._is_product_kit(titulo)
                attributes.append({
                    "id": "IS_FACTORY_KIT",
                    "value_id": "242085" if is_kit else "242084"  # Sim/Não
                })
            
            elif attr_id == 'ASSEMBLY_MANUAL_INCLUDED':
                attributes.append({
                    "id": "ASSEMBLY_MANUAL_INCLUDED",
                    "value_id": "242084"  # "Não"
                })
            
            elif attr_id == 'SIZE_GRID_ID':
                # Para produtos não-vestuário, usar "Tamanho único"
                default_value = self._find_default_list_value(
                    attr.get('values', []), 
                    ['tamanho único', 'único', 'não se aplica', 'standard', 'padrão']
                )
                if not default_value and attr.get('values'):
                    # Se não encontrou um valor padrão, usar o primeiro disponível
                    default_value = attr.get('values')[0].get('id')
                
                if default_value:
                    attributes.append({
                        "id": "SIZE_GRID_ID",
                        "value_id": default_value
                    })
                else:
                    # Fallback final - usar um valor genérico conhecido
                    attributes.append({
                        "id": "SIZE_GRID_ID",
                        "value_id": "242084"  # Valor genérico para "Não se aplica"
                    })
            
            elif attr.get('value_type') == 'boolean':
                # Para atributos booleanos, usar "Não" como padrão
                default_value = self._find_default_list_value(
                    attr.get('values', []),
                    ['não', 'no', 'false']
                )
                if default_value:
                    attributes.append({
                        "id": attr_id,
                        "value_id": default_value
                    })
        
        return attributes
    
    def _get_required_attributes_fallback(self, category_id, titulo, produto_dados):
        """Método fallback para gerar atributos quando API falha"""
        attributes = []
        
        # Obter atributos obrigatórios da categoria (método antigo)
        required_attrs = self._check_category_attributes(category_id)
        
        # Adicionar EMPTY_GTIN_REASON se GTIN for obrigatório
        if 'GTIN' in required_attrs:
            gtin_attr = required_attrs['GTIN']
            if gtin_attr.get('required') or gtin_attr.get('conditional_required'):
                attributes.append({
                    "id": "EMPTY_GTIN_REASON",
                    "value_id": "17055159"  # "Kit"
                })
        
        # Adicionar BRAND (Fabricante) se obrigatório
        if 'BRAND' in required_attrs:
            marca = self._extract_brand_from_title(titulo)
            if hasattr(produto_dados, 'marca') and produto_dados.marca:
                marca = produto_dados.marca
            
            attributes.append({
                "id": "BRAND",
                "value_name": marca
            })
        
        # Adicionar outros atributos básicos
        if 'PIECES_NUMBER' in required_attrs:
            num_pecas = self._extract_pieces_number(titulo)
            attributes.append({
                "id": "PIECES_NUMBER",
                "value_name": num_pecas
            })
        
        if 'IS_FACTORY_KIT' in required_attrs:
            is_kit = self._is_product_kit(titulo)
            attributes.append({
                "id": "IS_FACTORY_KIT",
                "value_id": "242085" if is_kit else "242084"
            })
        
        return attributes


    def publicar_produto(self, produto):
        """Publica um produto no Mercado Livre com validação e fallback inteligente"""

        pictures = [
            {"source": img.url_imagem}
            for img in ProdutoImagem.objects.filter(produto_codigo=produto.produto_codigo, ativo=True).order_by("ordem")
            if img.url_imagem
        ]

        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")

        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")

        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")

        # Usar mapeamento interno de categorias
        category_id = self._get_category_without_gtin(titulo, produto.categoria_marketplace)
        attributes = self._get_required_attributes(category_id, titulo, produto_dados)

        payload = {
            "title": titulo[:60],
            "category_id": category_id,
            "price": preco,
            "currency_id": "BRL",
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "buying_mode": "buy_it_now",
            "listing_type_id": "bronze",  # Sempre bronze para evitar exigência de imagens
            "condition": "new",
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            },
            "shipping": {
                "mode": "not_specified"
            },
            "attributes": attributes
        }

        # Só adiciona imagens e muda para gold_special se tiver imagens
        if pictures:
            payload["pictures"] = pictures[:10]
            # Comentado para evitar erro de imagens obrigatórias
            # payload["listing_type_id"] = "gold_special"

        print(json.dumps(payload, indent=2, ensure_ascii=False))

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.BASE_URL}/items", json=payload, headers=headers)

        if response.status_code != 201:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                details = [
                    f"{cause.get('code', 'campo_desconhecido')}: {cause.get('message', 'erro não especificado')}"
                    for cause in error_data.get('cause', [])
                ]
                raise Exception(f"Erro na API do ML: {error_message}. Detalhes: {'; '.join(details) or error_data}")
            except ValueError:
                raise Exception(f"Erro na API do ML (Status {response.status_code}): {response.text}")

        return response.json()

    def atualizar_produto(self, item_id, produto):
        """Atualiza um produto já publicado no Mercado Livre"""
        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")
            
        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")
            
        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")
            
        payload = {
            "title": titulo[:60],
            "price": preco,
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            }
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                error_details = []
                
                if 'cause' in error_data:
                    for cause in error_data['cause']:
                        field = cause.get('code', 'campo_desconhecido')
                        message = cause.get('message', 'erro não especificado')
                        error_details.append(f"{field}: {message}")
                
                if error_details:
                    full_error = f"{error_message}. Detalhes: {'; '.join(error_details)}"
                else:
                    full_error = f"{error_message}. Response completo: {error_data}"
                    
                raise Exception(f"Erro ao atualizar no ML: {full_error}")
            except ValueError:
                raise Exception(f"Erro ao atualizar no ML (Status {response.status_code}): {response.text}")
            
        return response.json()
    
    def pausar_produto(self, item_id):
        """Pausa um produto no Mercado Livre"""
        payload = {"status": "paused"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def reativar_produto(self, item_id):
        """Reativa um produto pausado no Mercado Livre"""
        payload = {"status": "active"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def _get_cached_categories(self):
        """Obtém categorias do cache ou da API se necessário"""
        cache_key = 'ml_categories_all'
        categories = cache.get(cache_key)
        
        if not categories:
            print("Cache de categorias vazio. Baixando da API...")
            categories = self._fetch_all_categories()
            if categories:
                # Cache por 24 horas
                cache.set(cache_key, categories, 60 * 60 * 24)
                print(f"Cache atualizado com {len(categories)} categorias")
        else:
            print(f"Usando cache com {len(categories)} categorias")
        
        return categories or []
    
    def _fetch_all_categories(self):
        """Baixa todas as categorias da API do Mercado Livre (sem autenticação)"""
        try:
            # API pública não requer token
            response = requests.get(f"{self.BASE_URL}/sites/MLB/categories/all")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Erro ao buscar categorias: {response.status_code}")
                return None
        except Exception as e:
            print(f"Erro ao buscar categorias: {e}")
            return None
    
    def _find_leaf_categories(self, search_terms):
        """Encontra categorias folha baseadas em termos de busca"""
        categories = self._get_cached_categories()
        if not categories:
            return []
        
        leaf_categories = []
        search_terms_upper = [term.upper() for term in search_terms]
        
        def is_leaf_category(category):
            # Uma categoria é folha se não tem children_categories ou se está vazio
            children = category.get('children_categories', [])
            return not children or len(children) == 0
        
        def search_in_category(category, path=""):
            if not isinstance(category, dict):
                return
                
            current_path = f"{path} > {category.get('name', '')}" if path else category.get('name', '')
            
            # Se é folha, verifica se contém algum termo de busca
            if is_leaf_category(category):
                category_text = f"{category.get('name', '')} {category.get('id', '')} {current_path}".upper()
                for term in search_terms_upper:
                    if term in category_text:
                        leaf_categories.append({
                            'id': category.get('id', ''),
                            'name': category.get('name', ''),
                            'path': current_path,
                            'total_items': category.get('total_items_in_this_category', 0)
                        })
                        break
            
            # Busca recursivamente nos filhos
            children = category.get('children_categories', [])
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        search_in_category(child, current_path)
        
        # Busca em todas as categorias
        if isinstance(categories, dict):
            # Se categories é um dicionário com IDs como chaves
            for cat_id, category in categories.items():
                if isinstance(category, dict):
                    search_in_category(category)
        elif isinstance(categories, list):
            # Se categories é uma lista
            for category in categories:
                if isinstance(category, dict):
                    search_in_category(category)
        
        # Ordena por número de itens (mais populares primeiro)
        leaf_categories.sort(key=lambda x: x.get('total_items', 0), reverse=True)
        return leaf_categories
    
    def _get_best_category_for_product(self, titulo, categoria_marketplace=None):
        """Encontra a melhor categoria folha para o produto"""
        # Primeiro, tenta usar a predição da API do ML
        predicted_category = self._get_category_prediction(titulo)
        if predicted_category:
            # Verifica se a categoria predita é folha
            try:
                attrs = self._check_category_attributes(predicted_category)
                if attrs is not None:  # Categoria existe
                    print(f"Usando categoria predita pela API: {predicted_category}")
                    return predicted_category
            except:
                pass
        
        search_terms = []
        
        # Adiciona categoria do marketplace se fornecida
        if categoria_marketplace:
            search_terms.append(categoria_marketplace)
        
        # Extrai palavras-chave do título
        titulo_words = titulo.upper().split()
        keywords = ['PRATO', 'TALHER', 'FAQUEIRO', 'CRISTAL', 'CHUMBO', 'TAMPA', 
                   'PEARL', 'BOLEIRA', 'WOLFF', 'COZINHA', 'UTENSILIO', 'DECORACAO']
        
        for word in titulo_words:
            if any(keyword in word for keyword in keywords):
                search_terms.append(word)
        
        # Adiciona termos genéricos baseados no título
        if any(word in titulo.upper() for word in ['PRATO', 'BOLEIRA', 'TAMPA']):
            search_terms.extend(['PRATOS', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['TALHER', 'FAQUEIRO']):
            search_terms.extend(['TALHERES', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['CRISTAL', 'DECORACAO']):
            search_terms.extend(['DECORAÇÃO', 'OBJETOS DECORATIVOS', 'CASA'])
        
        if not search_terms:
            search_terms = ['UTENSÍLIOS', 'COZINHA', 'CASA']  # Fallback genérico
        
        print(f"Buscando categorias para: {search_terms}")
        
        # Busca categorias folha
        leaf_categories = self._find_leaf_categories(search_terms)
        
        if leaf_categories:
            best_category = leaf_categories[0]  # Primeira (mais popular)
            print(f"Categoria encontrada: {best_category['id']} - {best_category['name']} ({best_category['path']}) - {best_category['total_items']} itens")
            return best_category['id']
        
        # Fallback para categoria conhecida e válida
        print("Nenhuma categoria específica encontrada. Usando categoria predita como fallback.")
        return predicted_category or "MLB1953"  # Mais Categorias
    
    def listar_categorias_sugeridas(self, titulo, categoria_marketplace=None):
        """Lista categorias sugeridas para o produto com informações sobre atributos obrigatórios"""
        categorias_sugeridas = []
        
        # 1. Categoria predita pela API do ML
        predicted_category = self._get_category_prediction(titulo)
        if predicted_category:
            attrs = self._check_category_attributes(predicted_category)
            categorias_sugeridas.append({
                'id': predicted_category,
                'nome': self._get_category_name(predicted_category),
                'tipo': 'Predição da API',
                'atributos_obrigatorios': list(attrs.keys()) if attrs else [],
                'exige_gtin': 'GTIN' in attrs and (attrs['GTIN'].get('required') or attrs['GTIN'].get('conditional_required')),
                'exige_size_grid': 'SIZE_GRID_ID' in attrs and (attrs['SIZE_GRID_ID'].get('required') or attrs['SIZE_GRID_ID'].get('conditional_required'))
            })
        
        # 2. Buscar categorias por palavras-chave
        search_terms = []
        if categoria_marketplace:
            search_terms.append(categoria_marketplace)
        
        # Extrair termos do título
        titulo_words = titulo.upper().split()
        keywords = ['PRATO', 'TALHER', 'FAQUEIRO', 'CRISTAL', 'CHUMBO', 'TAMPA', 
                   'PEARL', 'BOLEIRA', 'WOLFF', 'COZINHA', 'UTENSILIO', 'DECORACAO']
        
        for word in titulo_words:
            if any(keyword in word for keyword in keywords):
                search_terms.append(word)
        
        # Adicionar termos genéricos
        if any(word in titulo.upper() for word in ['PRATO', 'BOLEIRA', 'TAMPA']):
            search_terms.extend(['PRATOS', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['TALHER', 'FAQUEIRO']):
            search_terms.extend(['TALHERES', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['CRISTAL', 'DECORACAO']):
            search_terms.extend(['DECORAÇÃO', 'OBJETOS DECORATIVOS', 'CASA'])
        
        # Buscar categorias folha
        leaf_categories = self._find_leaf_categories(search_terms)
        
        for cat in leaf_categories[:5]:  # Limitar a 5 sugestões
            if cat['id'] not in [c['id'] for c in categorias_sugeridas]:  # Evitar duplicatas
                attrs = self._check_category_attributes(cat['id'])
                categorias_sugeridas.append({
                    'id': cat['id'],
                    'nome': cat['name'],
                    'caminho': cat['path'],
                    'total_itens': cat['total_items'],
                    'tipo': 'Busca por palavras-chave',
                    'atributos_obrigatorios': list(attrs.keys()) if attrs else [],
                    'exige_gtin': 'GTIN' in attrs and (attrs['GTIN'].get('required') or attrs['GTIN'].get('conditional_required')),
                    'exige_size_grid': 'SIZE_GRID_ID' in attrs and (attrs['SIZE_GRID_ID'].get('required') or attrs['SIZE_GRID_ID'].get('conditional_required'))
                })
        
        # 3. Adicionar categorias seguras (que não exigem GTIN nem SIZE_GRID_ID)
        categorias_seguras = [
            'MLB1574',  # Casa, Móveis e Decoração
            'MLB1953',  # Mais Categorias
            'MLB1499'   # Indústria e Comércio
        ]
        
        for cat_id in categorias_seguras:
            if cat_id not in [c['id'] for c in categorias_sugeridas]:
                attrs = self._check_category_attributes(cat_id)
                categorias_sugeridas.append({
                    'id': cat_id,
                    'nome': self._get_category_name(cat_id),
                    'tipo': 'Categoria segura',
                    'atributos_obrigatorios': list(attrs.keys()) if attrs else [],
                    'exige_gtin': 'GTIN' in attrs and (attrs['GTIN'].get('required') or attrs['GTIN'].get('conditional_required')),
                    'exige_size_grid': 'SIZE_GRID_ID' in attrs and (attrs['SIZE_GRID_ID'].get('required') or attrs['SIZE_GRID_ID'].get('conditional_required'))
                })
        
        return categorias_sugeridas
    
    def _get_category_name(self, category_id):
        """Obtém o nome de uma categoria pelo ID"""
        try:
            response = requests.get(f"{self.BASE_URL}/categories/{category_id}")
            if response.status_code == 200:
                data = response.json()
                return data.get('name', f'Categoria {category_id}')
        except:
            pass
        return f'Categoria {category_id}'
    

    
    def _get_required_attributes(self, category_id, titulo, produto_dados):
        """Gera os atributos obrigatórios para a categoria do produto"""
        attributes = []
        
        # Obter atributos obrigatórios da categoria
        required_attrs = self._check_category_attributes(category_id)
        
        # Adicionar EMPTY_GTIN_REASON se GTIN for obrigatório
        if 'GTIN' in required_attrs:
            gtin_attr = required_attrs['GTIN']
            if gtin_attr.get('required') or gtin_attr.get('conditional_required'):
                # Use diferentes valores baseados no tipo de produto
                if any(word in titulo.upper() for word in ['KIT', 'CONJUNTO', 'FAQUEIRO']):
                    empty_gtin_value = "17055159"  # "Kit"
                elif any(word in titulo.upper() for word in ['ARTESANAL', 'PERSONALIZADO', 'CUSTOMIZADO']):
                    empty_gtin_value = "2230284"  # "O produto não possui código de barras"
                else:
                    empty_gtin_value = "17055159"  # "Kit" como padrão
                
                attributes.append({
                    "id": "EMPTY_GTIN_REASON",
                    "value_id": empty_gtin_value
                })
        
        # Adicionar BRAND (Fabricante) se obrigatório
        if 'BRAND' in required_attrs:
            # Tentar extrair marca do título ou usar genérica
            marca = "Genérica"
            titulo_upper = titulo.upper()
            if 'WOLFF' in titulo_upper:
                marca = "Wolff"
            elif 'ST.JAMES' in titulo_upper:
                marca = "St. James"
            elif 'FENDI' in titulo_upper:
                marca = "Fendi"
            elif hasattr(produto_dados, 'marca') and produto_dados.marca:
                marca = produto_dados.marca
            elif hasattr(produto_dados, 'prod_marc') and produto_dados.prod_marc:
                marca = produto_dados.prod_marc.nome if hasattr(produto_dados.prod_marc, 'nome') else str(produto_dados.prod_marc)
            
            attributes.append({
                "id": "BRAND",
                "value_name": marca
            })
        
        # Adicionar MODEL (Modelo) se obrigatório
        if 'MODEL' in required_attrs:
            model_attr = required_attrs['MODEL']
            if model_attr.get('required') or model_attr.get('conditional_required'):
                # Tentar extrair modelo do título ou criar um baseado no código do produto
                modelo = titulo[:50]  # Usar título como modelo por padrão
                
                # Se tiver código do produto, usar como modelo
                if hasattr(produto_dados, 'prod_codi') and produto_dados.prod_codi:
                    modelo = f"{produto_dados.prod_codi} - {titulo[:30]}"
                elif hasattr(produto_dados, 'codigo') and produto_dados.codigo:
                    modelo = f"{produto_dados.codigo} - {titulo[:30]}"
                
                # Limitar tamanho
                modelo = modelo[:50]
                
                attributes.append({
                    "id": "MODEL",
                    "value_name": modelo
                })
        
        # Adicionar SIZE_GRID_ID se obrigatório (para produtos de moda/vestuário)
        if 'SIZE_GRID_ID' in required_attrs:
            size_attr = required_attrs['SIZE_GRID_ID']
            if size_attr.get('required') or size_attr.get('conditional_required'):
                attributes.append({
                    "id": "SIZE_GRID_ID",
                    "value_id": "242084"  # "Tamanho único"
                })
        
        # Adicionar ASSEMBLY_MANUAL_INCLUDED se obrigatório
        if 'ASSEMBLY_MANUAL_INCLUDED' in required_attrs:
            assembly_attr = required_attrs['ASSEMBLY_MANUAL_INCLUDED']
            if assembly_attr.get('required') or assembly_attr.get('conditional_required'):
                attributes.append({
                    "id": "ASSEMBLY_MANUAL_INCLUDED",
                    "value_id": "242085"  # "Não"
                })
        
        # Adicionar IS_FACTORY_KIT se obrigatório
        if 'IS_FACTORY_KIT' in required_attrs:
            kit_attr = required_attrs['IS_FACTORY_KIT']
            if kit_attr.get('required') or kit_attr.get('conditional_required'):
                attributes.append({
                    "id": "IS_FACTORY_KIT",
                    "value_id": "242085"  # "Não"
                })
        
        # Adicionar PIECES_NUMBER se obrigatório
        if 'PIECES_NUMBER' in required_attrs:
            pieces_attr = required_attrs['PIECES_NUMBER']
            if pieces_attr.get('required') or pieces_attr.get('conditional_required'):
                # Tentar extrair número de peças do título
                pieces = "1"  # padrão
                titulo_upper = titulo.upper()
                
                # Buscar padrões como "6 PEÇAS", "SET 12", etc.
                import re
                match = re.search(r'(\d+)\s*PE[ÇC]AS?|SET\s*(\d+)|(\d+)\s*PC|(\d+)\s*UNID', titulo_upper)
                if match:
                    pieces = next(g for g in match.groups() if g)
                elif 'FAQUEIRO' in titulo_upper:
                    # Faqueiros normalmente vêm em conjuntos
                    pieces = "24"  # comum para faqueiros
                
                attributes.append({
                    "id": "PIECES_NUMBER",
                    "value_name": pieces
                })
        
        return attributes


    def publicar_produto(self, produto):
        """Publica um produto no Mercado Livre com validação e fallback inteligente"""

        pictures = [
            {"source": img.url_imagem}
            for img in ProdutoImagem.objects.filter(produto_codigo=produto.produto_codigo, ativo=True).order_by("ordem")
            if img.url_imagem
        ]

        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")

        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")

        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")

        # Usar mapeamento interno de categorias
        category_id = self._get_category_without_gtin(titulo, produto.categoria_marketplace)
        attributes = self._get_required_attributes(category_id, titulo, produto_dados)

        payload = {
            "title": titulo[:60],
            "category_id": category_id,
            "price": preco,
            "currency_id": "BRL",
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "buying_mode": "buy_it_now",
            "listing_type_id": "bronze",  # Sempre bronze para evitar exigência de imagens
            "condition": "new",
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            },
            "shipping": {
                "mode": "not_specified"
            },
            "attributes": attributes
        }

        # Só adiciona imagens e muda para gold_special se tiver imagens
        if pictures:
            payload["pictures"] = pictures[:10]
            # Comentado para evitar erro de imagens obrigatórias
            # payload["listing_type_id"] = "gold_special"

        print(json.dumps(payload, indent=2, ensure_ascii=False))

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.BASE_URL}/items", json=payload, headers=headers)

        if response.status_code != 201:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                details = [
                    f"{cause.get('code', 'campo_desconhecido')}: {cause.get('message', 'erro não especificado')}"
                    for cause in error_data.get('cause', [])
                ]
                raise Exception(f"Erro na API do ML: {error_message}. Detalhes: {'; '.join(details) or error_data}")
            except ValueError:
                raise Exception(f"Erro na API do ML (Status {response.status_code}): {response.text}")

        return response.json()

    def atualizar_produto(self, item_id, produto):
        """Atualiza um produto já publicado no Mercado Livre"""
        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")
            
        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")
            
        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")
            
        payload = {
            "title": titulo[:60],
            "price": preco,
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            }
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                error_details = []
                
                if 'cause' in error_data:
                    for cause in error_data['cause']:
                        field = cause.get('code', 'campo_desconhecido')
                        message = cause.get('message', 'erro não especificado')
                        error_details.append(f"{field}: {message}")
                
                if error_details:
                    full_error = f"{error_message}. Detalhes: {'; '.join(error_details)}"
                else:
                    full_error = f"{error_message}. Response completo: {error_data}"
                    
                raise Exception(f"Erro ao atualizar no ML: {full_error}")
            except ValueError:
                raise Exception(f"Erro ao atualizar no ML (Status {response.status_code}): {response.text}")
            
        return response.json()
    
    def pausar_produto(self, item_id):
        """Pausa um produto no Mercado Livre"""
        payload = {"status": "paused"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def reativar_produto(self, item_id):
        """Reativa um produto pausado no Mercado Livre"""
        payload = {"status": "active"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

    def _get_cached_categories(self):
        """Obtém categorias do cache ou da API se necessário"""
        cache_key = 'ml_categories_all'
        categories = cache.get(cache_key)
        
        if not categories:
            print("Cache de categorias vazio. Baixando da API...")
            categories = self._fetch_all_categories()
            if categories:
                # Cache por 24 horas
                cache.set(cache_key, categories, 60 * 60 * 24)
                print(f"Cache atualizado com {len(categories)} categorias")
        else:
            print(f"Usando cache com {len(categories)} categorias")
        
        return categories or []
    
    def _fetch_all_categories(self):
        """Baixa todas as categorias da API do Mercado Livre (sem autenticação)"""
        try:
            # API pública não requer token
            response = requests.get(f"{self.BASE_URL}/sites/MLB/categories/all")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Erro ao buscar categorias: {response.status_code}")
                return None
        except Exception as e:
            print(f"Erro ao buscar categorias: {e}")
            return None
    
    def _find_leaf_categories(self, search_terms):
        """Encontra categorias folha baseadas em termos de busca"""
        categories = self._get_cached_categories()
        if not categories:
            return []
        
        leaf_categories = []
        search_terms_upper = [term.upper() for term in search_terms]
        
        def is_leaf_category(category):
            # Uma categoria é folha se não tem children_categories ou se está vazio
            children = category.get('children_categories', [])
            return not children or len(children) == 0
        
        def search_in_category(category, path=""):
            if not isinstance(category, dict):
                return
                
            current_path = f"{path} > {category.get('name', '')}" if path else category.get('name', '')
            
            # Se é folha, verifica se contém algum termo de busca
            if is_leaf_category(category):
                category_text = f"{category.get('name', '')} {category.get('id', '')} {current_path}".upper()
                for term in search_terms_upper:
                    if term in category_text:
                        leaf_categories.append({
                            'id': category.get('id', ''),
                            'name': category.get('name', ''),
                            'path': current_path,
                            'total_items': category.get('total_items_in_this_category', 0)
                        })
                        break
            
            # Busca recursivamente nos filhos
            children = category.get('children_categories', [])
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        search_in_category(child, current_path)
        
        # Busca em todas as categorias
        if isinstance(categories, dict):
            # Se categories é um dicionário com IDs como chaves
            for cat_id, category in categories.items():
                if isinstance(category, dict):
                    search_in_category(category)
        elif isinstance(categories, list):
            # Se categories é uma lista
            for category in categories:
                if isinstance(category, dict):
                    search_in_category(category)
        
        # Ordena por número de itens (mais populares primeiro)
        leaf_categories.sort(key=lambda x: x.get('total_items', 0), reverse=True)
        return leaf_categories
    
    def _get_best_category_for_product(self, titulo, categoria_marketplace=None):
        """Encontra a melhor categoria folha para o produto"""
        # Primeiro, tenta usar a predição da API do ML
        predicted_category = self._get_category_prediction(titulo)
        if predicted_category:
            # Verifica se a categoria predita é folha
            try:
                attrs = self._check_category_attributes(predicted_category)
                if attrs is not None:  # Categoria existe
                    print(f"Usando categoria predita pela API: {predicted_category}")
                    return predicted_category
            except:
                pass
        
        search_terms = []
        
        # Adiciona categoria do marketplace se fornecida
        if categoria_marketplace:
            search_terms.append(categoria_marketplace)
        
        # Extrai palavras-chave do título
        titulo_words = titulo.upper().split()
        keywords = ['PRATO', 'TALHER', 'FAQUEIRO', 'CRISTAL', 'CHUMBO', 'TAMPA', 
                   'PEARL', 'BOLEIRA', 'WOLFF', 'COZINHA', 'UTENSILIO', 'DECORACAO']
        
        for word in titulo_words:
            if any(keyword in word for keyword in keywords):
                search_terms.append(word)
        
        # Adiciona termos genéricos baseados no título
        if any(word in titulo.upper() for word in ['PRATO', 'BOLEIRA', 'TAMPA']):
            search_terms.extend(['PRATOS', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['TALHER', 'FAQUEIRO']):
            search_terms.extend(['TALHERES', 'UTENSÍLIOS', 'COZINHA', 'MESA'])
        elif any(word in titulo.upper() for word in ['CRISTAL', 'DECORACAO']):
            search_terms.extend(['DECORAÇÃO', 'OBJETOS DECORATIVOS', 'CASA'])
        
        if not search_terms:
            search_terms = ['UTENSÍLIOS', 'COZINHA', 'CASA']  # Fallback genérico
        
        print(f"Buscando categorias para: {search_terms}")
        
        # Busca categorias folha
        leaf_categories = self._find_leaf_categories(search_terms)
        
        if leaf_categories:
            best_category = leaf_categories[0]  # Primeira (mais popular)
            print(f"Categoria encontrada: {best_category['id']} - {best_category['name']} ({best_category['path']}) - {best_category['total_items']} itens")
            return best_category['id']
        
        # Fallback para categoria conhecida e válida
        print("Nenhuma categoria específica encontrada. Usando categoria predita como fallback.")
        return predicted_category or "MLB1953"  # Mais Categorias
    
    def _get_required_attributes(self, category_id, titulo, produto_dados):
        """Gera os atributos obrigatórios para a categoria do produto"""
        attributes = []
        
        # Obter atributos obrigatórios da categoria
        required_attrs = self._check_category_attributes(category_id)
        
        # Adicionar EMPTY_GTIN_REASON se GTIN for obrigatório
        if 'GTIN' in required_attrs:
            gtin_attr = required_attrs['GTIN']
            if gtin_attr.get('required') or gtin_attr.get('conditional_required'):
                attributes.append({
                    "id": "EMPTY_GTIN_REASON",
                    "value_id": "17055159"  # "Kit" - mais apropriado para faqueiros/conjuntos
                })
        
        # Adicionar BRAND (Fabricante) se obrigatório
        if 'BRAND' in required_attrs:
            # Tentar extrair marca do título ou usar genérica
            marca = "Genérica"
            titulo_upper = titulo.upper()
            if 'WOLFF' in titulo_upper:
                marca = "Wolff"
            elif 'ST.JAMES' in titulo_upper:
                marca = "St. James"
            elif 'FENDI' in titulo_upper:
                marca = "Fendi"
            elif hasattr(produto_dados, 'marca') and produto_dados.marca:
                marca = produto_dados.marca
            
            attributes.append({
                "id": "BRAND",
                "value_name": marca
            })
        
        # Adicionar ASSEMBLY_MANUAL_INCLUDED (Inclui manual de montagem)
        if 'ASSEMBLY_MANUAL_INCLUDED' in required_attrs:
            attributes.append({
                "id": "ASSEMBLY_MANUAL_INCLUDED",
                "value_id": "242084"  # "Não" - padrão para utensílios
            })
        
        # Adicionar IS_FACTORY_KIT se obrigatório (para conjuntos/kits)
        if 'IS_FACTORY_KIT' in required_attrs:
            # Verificar se é um kit baseado no título
            is_kit = any(palavra in titulo.upper() for palavra in ['KIT', 'CONJUNTO', 'FAQUEIRO', 'JOGO', 'ESTOJO'])
            attributes.append({
                "id": "IS_FACTORY_KIT",
                "value_id": "242085" if is_kit else "242084"  # Sim/Não
            })
        
        # Adicionar PIECES_NUMBER se obrigatório (número de peças)
        if 'PIECES_NUMBER' in required_attrs:
            # Tentar extrair número de peças do título
            import re
            pecas_match = re.search(r'(\\d+)\\s*pe[çc]as?', titulo, re.IGNORECASE)
            if not pecas_match:
                pecas_match = re.search(r'(\\d+)\\s*pcs', titulo, re.IGNORECASE)
            
            if pecas_match:
                num_pecas = pecas_match.group(1)
            else:
                # Fallback baseado no tipo de produto
                if 'FAQUEIRO' in titulo.upper() or 'ESTOJO' in titulo.upper():
                    # Extrair número do título se possível
                    num_match = re.search(r'(\\d+)', titulo)
                    num_pecas = num_match.group(1) if num_match else "101"
                elif 'JOGO' in titulo.upper() or 'KIT' in titulo.upper():
                    num_pecas = "6"   # Jogo típico
                else:
                    num_pecas = "1"   # Peça única
            
            attributes.append({
                "id": "PIECES_NUMBER",
                "value_name": num_pecas
            })
        
        return attributes


    def publicar_produto(self, produto):
        """Publica um produto no Mercado Livre com validação e fallback inteligente"""

        pictures = [
            {"source": img.url_imagem}
            for img in ProdutoImagem.objects.filter(produto_codigo=produto.produto_codigo, ativo=True).order_by("ordem")
            if img.url_imagem
        ]

        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")

        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")

        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")

        # Usar mapeamento interno de categorias
        category_id = self._get_category_without_gtin(titulo, produto.categoria_marketplace)
        attributes = self._get_required_attributes(category_id, titulo, produto_dados)

        payload = {
            "title": titulo[:60],
            "category_id": category_id,
            "price": preco,
            "currency_id": "BRL",
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "buying_mode": "buy_it_now",
            "listing_type_id": "bronze",  # Sempre bronze para evitar exigência de imagens
            "condition": "new",
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            },
            "shipping": {
                "mode": "not_specified"
            },
            "attributes": attributes
        }

        # Só adiciona imagens e muda para gold_special se tiver imagens
        if pictures:
            payload["pictures"] = pictures[:10]
            # Comentado para evitar erro de imagens obrigatórias
            # payload["listing_type_id"] = "gold_special"

        print(json.dumps(payload, indent=2, ensure_ascii=False))

        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.post(f"{self.BASE_URL}/items", json=payload, headers=headers)

        if response.status_code != 201:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                details = [
                    f"{cause.get('code', 'campo_desconhecido')}: {cause.get('message', 'erro não especificado')}"
                    for cause in error_data.get('cause', [])
                ]
                raise Exception(f"Erro na API do ML: {error_message}. Detalhes: {'; '.join(details) or error_data}")
            except ValueError:
                raise Exception(f"Erro na API do ML (Status {response.status_code}): {response.text}")

        return response.json()

    def atualizar_produto(self, item_id, produto):
        """Atualiza um produto já publicado no Mercado Livre"""
        produto_dados = produto.get_produto(slug=self.slug)
        if not produto_dados:
            raise Exception("Produto não encontrado no sistema principal")
            
        preco = float(produto_dados.preco_vista or produto_dados.preco_prazo or 0)
        if preco <= 0:
            raise Exception("Produto deve ter um preço válido maior que zero")
            
        titulo = produto.titulo_customizado or produto_dados.nome
        if not titulo or len(titulo.strip()) == 0:
            raise Exception("Produto deve ter um título válido")
            
        payload = {
            "title": titulo[:60],
            "price": preco,
            "available_quantity": max(int(produto_dados.saldo or 0), 1),
            "description": {
                "plain_text": (produto.descricao_melhorada or produto_dados.nome or titulo)[:50000]
            }
        }
        
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        
        if response.status_code not in [200, 201]:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Erro desconhecido')
                error_details = []
                
                if 'cause' in error_data:
                    for cause in error_data['cause']:
                        field = cause.get('code', 'campo_desconhecido')
                        message = cause.get('message', 'erro não especificado')
                        error_details.append(f"{field}: {message}")
                
                if error_details:
                    full_error = f"{error_message}. Detalhes: {'; '.join(error_details)}"
                else:
                    full_error = f"{error_message}. Response completo: {error_data}"
                    
                raise Exception(f"Erro ao atualizar no ML: {full_error}")
            except ValueError:
                raise Exception(f"Erro ao atualizar no ML (Status {response.status_code}): {response.text}")
            
        return response.json()
    
    def pausar_produto(self, item_id):
        """Pausa um produto no Mercado Livre"""
        payload = {"status": "paused"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def reativar_produto(self, item_id):
        """Reativa um produto pausado no Mercado Livre"""
        payload = {"status": "active"}
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(f"{self.BASE_URL}/items/{item_id}", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
                        

  