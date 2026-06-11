# Localidades/services/ibge_service.py
"""
Integração com a API de Localidades do IBGE.
https://servicodados.ibge.gov.br/api/docs/localidades

Responsabilidades:
- Listar estados / países / municípios direto da API
- Sincronizar (seed) estados e países para o banco da licença
- Obter ou criar uma cidade a partir do código IBGE do município
"""

import requests

from Localidades.models import Estados, Paises, Cidades

IBGE_BASE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades"

# Código M49 do Brasil na API de países do IBGE
CODIGO_PAIS_BRASIL = 76


class IBGEServiceError(Exception):
    """Erro de comunicação ou de dados com a API do IBGE."""


class IBGEService:

    TIMEOUT = 10

    # ------------------------------------------------------------------
    # Chamadas à API
    # ------------------------------------------------------------------

    @classmethod
    def _get(cls, path):
        url = f"{IBGE_BASE_URL}{path}"
        try:
            resp = requests.get(url, timeout=cls.TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise IBGEServiceError(f"Falha ao consultar IBGE ({url}): {exc}") from exc

    @classmethod
    def listar_estados_api(cls):
        """Lista as 27 UFs. [{id, sigla, nome, regiao}, ...]"""
        return cls._get("/estados?orderBy=nome")

    @classmethod
    def listar_paises_api(cls):
        """Lista os países. [{id: {M49, ...}, nome, ...}, ...]"""
        return cls._get("/paises?orderBy=nome")

    @classmethod
    def buscar_municipio_api(cls, codigo_ibge):
        """Busca um município pelo código IBGE (7 dígitos)."""
        dados = cls._get(f"/municipios/{int(codigo_ibge)}")
        # A API retorna [] quando o código não existe
        if not dados:
            raise IBGEServiceError(
                f"Município com código IBGE {codigo_ibge} não encontrado."
            )
        return dados

    @classmethod
    def listar_municipios_por_uf_api(cls, uf_id):
        """Lista os municípios de uma UF (id ou sigla)."""
        return cls._get(f"/estados/{uf_id}/municipios?orderBy=nome")

    # ------------------------------------------------------------------
    # Sincronização com o banco da licença (multibanco)
    # ------------------------------------------------------------------

    @classmethod
    def sincronizar_estados(cls, banco):
        """
        Cria/atualiza todas as UFs no banco informado.
        Retorna {'criados': X, 'atualizados': Y}.
        """
        criados = 0
        atualizados = 0

        for uf in cls.listar_estados_api():
            _, created = Estados.objects.using(banco).update_or_create(
                esta_codi=uf["id"],
                defaults={
                    "esta_nome": (uf["nome"] or "").strip(),
                    "esta_sigl": (uf["sigla"] or "").strip().upper(),
                },
            )
            if created:
                criados += 1
            else:
                atualizados += 1

        return {"criados": criados, "atualizados": atualizados}

    @classmethod
    def sincronizar_paises(cls, banco):
        """
        Cria/atualiza todos os países no banco informado (código M49).
        Retorna {'criados': X, 'atualizados': Y}.
        """
        criados = 0
        atualizados = 0

        for pais in cls.listar_paises_api():
            codigo = (pais.get("id") or {}).get("M49")
            if not codigo:
                continue

            _, created = Paises.objects.using(banco).update_or_create(
                pais_codi=codigo,
                defaults={"pais_nome": (pais["nome"] or "").strip()},
            )
            if created:
                criados += 1
            else:
                atualizados += 1

        return {"criados": criados, "atualizados": atualizados}

    # ------------------------------------------------------------------
    # Cidades
    # ------------------------------------------------------------------

    @classmethod
    def _obter_ou_criar_pais_brasil(cls, banco):
        pais, _ = Paises.objects.using(banco).get_or_create(
            pais_codi=CODIGO_PAIS_BRASIL,
            defaults={"pais_nome": "Brasil"},
        )
        return pais

    @classmethod
    def _obter_ou_criar_estado(cls, banco, uf_dict):
        estado, _ = Estados.objects.using(banco).get_or_create(
            esta_codi=uf_dict["id"],
            defaults={
                "esta_nome": (uf_dict["nome"] or "").strip(),
                "esta_sigl": (uf_dict["sigla"] or "").strip().upper(),
            },
        )
        return estado

    @classmethod
    def obter_ou_criar_cidade(cls, banco, codigo_ibge):
        """
        Retorna a cidade do banco se já existir; caso contrário,
        busca o município na API do IBGE e cria a cidade (criando
        também estado e país se necessário).

        Retorna (cidade, criada: bool).
        """
        try:
            codigo_ibge = int(codigo_ibge)
        except (TypeError, ValueError):
            raise IBGEServiceError(f"Código IBGE inválido: {codigo_ibge!r}")

        cidade = Cidades.objects.using(banco).filter(cida_codi=codigo_ibge).first()
        if cidade:
            return cidade, False

        municipio = cls.buscar_municipio_api(codigo_ibge)
        uf = municipio["microrregiao"]["mesorregiao"]["UF"]

        estado = cls._obter_ou_criar_estado(banco, uf)
        pais = cls._obter_ou_criar_pais_brasil(banco)

        cidade = Cidades(
            cida_codi=municipio["id"],
            cida_nome=(municipio["nome"] or "").strip(),
            cida_esta=estado,
            cida_pais=pais,
            cida_sigl=estado.esta_sigl,
        )
        cidade.save(using=banco)

        return cidade, True