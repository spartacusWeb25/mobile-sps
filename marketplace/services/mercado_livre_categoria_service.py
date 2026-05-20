# marketplace/services/mercado_livre_categoria_service.py

import requests


class MercadoLivreCategoriaService:
    BASE_URL = "https://api.mercadolibre.com"

    def __init__(self, api_service):
        self.api_service = api_service

    def prever_categoria(self, titulo):
        if not titulo:
            return None

        params = {"q": titulo[:100], "limit": 1}

        # 1) Tenta predição via domain_discovery
        try:
            data = self.api_service.request(
                method="GET",
                endpoint="/sites/MLB/domain_discovery/search",
                params=params,
            )
        except Exception:
            data = None

        def _requires_gtin_or_size(category_id):
            if not category_id:
                return False
            try:
                attrs = self.buscar_atributos_obrigatorios(category_id)
                for a in attrs:
                    aid = a.get("id")
                    tags = a.get("tags", {})
                    if aid == "GTIN" and (tags.get("required") or tags.get("conditional_required")):
                        return True
                    if aid == "SIZE_GRID_ID" and (tags.get("required") or tags.get("conditional_required")):
                        return True
            except Exception:
                return False
            return False

        category_id = None

        if data:
            if isinstance(data, list) and len(data) > 0:
                candidate = data[0].get("category_id") or data[0].get("id")
            elif isinstance(data, dict):
                results = data.get("results") or data.get("categories") or data.get("suggestions")
                if isinstance(results, list) and len(results) > 0:
                    first = results[0]
                    if isinstance(first, dict):
                        candidate = first.get("category_id") or first.get("id") or first.get("category")
            else:
                candidate = None

            if candidate and not _requires_gtin_or_size(candidate):
                return candidate

        # 2) tentar /sites/MLB/search
        try:
            data2 = self.api_service.request(
                method="GET",
                endpoint="/sites/MLB/search",
                params=params,
            )
        except Exception:
            data2 = None

        if data2:
            if isinstance(data2, dict):
                results = data2.get("results") or data2.get("categories")
                if isinstance(results, list) and len(results) > 0:
                    first = results[0]
                    if isinstance(first, dict):
                        candidate2 = first.get("category_id") or first.get("id") or first.get("category")
                        if candidate2 and not _requires_gtin_or_size(candidate2):
                            return candidate2
            elif isinstance(data2, list) and len(data2) > 0:
                candidate2 = data2[0].get("category_id") or data2[0].get("id")
                if candidate2 and not _requires_gtin_or_size(candidate2):
                    return candidate2

        # 3) tentar categorias alternativas seguras
        safe_categories = ["MLB1574", "MLB1953", "MLB1499", "MLB1574"]
        for safe in safe_categories:
            try:
                if not _requires_gtin_or_size(safe):
                    return safe
            except Exception:
                continue

        # 4) fallback: retornar candidate (mesmo que exija atributos) ou None
        try:
            if 'candidate' in locals() and candidate:
                return candidate
        except Exception:
            pass

        return None

    def buscar_atributos_obrigatorios(self, category_id):
        if not category_id:
            return []

        data = self.api_service.request(
            method="GET",
            endpoint=f"/categories/{category_id}/attributes",
        )

        atributos = []

        for attr in data:
            tags = attr.get("tags", {})

            if tags.get("required") or tags.get("conditional_required"):
                atributos.append({
                    "id": attr.get("id"),
                    "name": attr.get("name"),
                    "value_type": attr.get("value_type"),
                    "values": attr.get("values", []),
                    "tags": tags,
                })

        return atributos