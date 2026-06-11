from decimal import Decimal, InvalidOperation


class FreteCidadeService:
    """Resolve o frete padrão a partir da cidade vinculada na entidade."""

    @staticmethod
    def normalizar_codigo_ibge(codigo_ibge):
        codigo = "".join(ch for ch in str(codigo_ibge or "").strip() if ch.isdigit())
        return codigo or None

    @classmethod
    def obter_cidade_por_codigo_ibge(cls, banco, codigo_ibge):
        codigo = cls.normalizar_codigo_ibge(codigo_ibge)
        if not codigo:
            return None

        try:
            codigo_int = int(codigo)
        except (TypeError, ValueError):
            return None

        from localidades.models import Cidades

        return (
            Cidades.objects.using(banco)
            .select_related("cida_esta", "cida_pais")
            .filter(cida_codi=codigo_int)
            .first()
        )

    @classmethod
    def _serializar_cidade_frete(cls, cidade, codigo_ibge):
        if not cidade:
            return None

        frete = getattr(cidade, "cida_fret", None)
        try:
            frete_decimal = Decimal(str(frete)) if frete is not None else None
        except (InvalidOperation, TypeError, ValueError):
            frete_decimal = None

        return {
            "codigo_ibge": cls.normalizar_codigo_ibge(codigo_ibge),
            "cidade_codigo": getattr(cidade, "cida_codi", None),
            "cidade_nome": getattr(cidade, "cida_nome", None),
            "cidade_sigla": getattr(cidade, "cida_sigl", None),
            "estado_nome": getattr(getattr(cidade, "cida_esta", None), "esta_nome", None),
            "pais_nome": getattr(getattr(cidade, "cida_pais", None), "pais_nome", None),
            "frete": float(frete_decimal) if frete_decimal is not None else None,
            "frete_formatado": f"{frete_decimal:.2f}" if frete_decimal is not None else "",
        }

    @classmethod
    def obter_frete_por_codigo_ibge(cls, banco, codigo_ibge):
        cidade = cls.obter_cidade_por_codigo_ibge(banco=banco, codigo_ibge=codigo_ibge)
        return cls._serializar_cidade_frete(cidade=cidade, codigo_ibge=codigo_ibge)

    @classmethod
    def mapear_fretes_por_codigos_ibge(cls, banco, codigos_ibge):
        codigos_normalizados = []
        codigo_to_int = {}
        for codigo in codigos_ibge or []:
            normalizado = cls.normalizar_codigo_ibge(codigo)
            if not normalizado:
                continue
            try:
                codigo_to_int[normalizado] = int(normalizado)
            except (TypeError, ValueError):
                continue
            codigos_normalizados.append(normalizado)

        if not codigos_normalizados:
            return {}

        from localidades.models import Cidades

        cidades = (
            Cidades.objects.using(banco)
            .select_related("cida_esta", "cida_pais")
            .filter(cida_codi__in=list(codigo_to_int.values()))
        )

        cidades_por_codigo = {str(getattr(cidade, "cida_codi", "")): cidade for cidade in cidades}
        mapa = {}
        for codigo in codigos_normalizados:
            cidade = cidades_por_codigo.get(codigo)
            if not cidade:
                mapa[codigo] = None
                continue
            mapa[codigo] = cls._serializar_cidade_frete(cidade=cidade, codigo_ibge=codigo)
        return mapa

    @classmethod
    def obter_frete_da_entidade(cls, banco, entidade):
        if not entidade:
            return None
        return cls.obter_frete_por_codigo_ibge(
            banco=banco,
            codigo_ibge=getattr(entidade, "enti_codi_cida", None),
        )

    @classmethod
    def montar_payload_autocomplete(cls, entidade, banco, text=None, label=None, frete_info=None):
        frete_info = frete_info or cls.obter_frete_da_entidade(banco=banco, entidade=entidade) or {}
        descricao = text or label or f"{entidade.enti_clie} - {entidade.enti_nome}"

        payload = {
            "id": str(entidade.enti_clie),
            "text": descricao,
            "label": descricao,
            "value": str(entidade.enti_clie),
            "enti_clie": str(entidade.enti_clie),
            "enti_nome": entidade.enti_nome,
            "enti_codi_cida": cls.normalizar_codigo_ibge(getattr(entidade, "enti_codi_cida", None)) or "",
            "frete_cidade": frete_info.get("frete"),
            "frete_cidade_formatado": frete_info.get("frete_formatado", ""),
            "cidade_ibge": frete_info.get("codigo_ibge")
            or cls.normalizar_codigo_ibge(getattr(entidade, "enti_codi_cida", None))
            or "",
            "cidade_nome": frete_info.get("cidade_nome") or getattr(entidade, "enti_cida", ""),
            "cidade_sigla": frete_info.get("cidade_sigla") or getattr(entidade, "enti_esta", ""),
            "estado_nome": frete_info.get("estado_nome"),
            "pais_nome": frete_info.get("pais_nome"),
        }
        return payload

    @classmethod
    def montar_payloads_autocomplete(cls, entidades, banco, descricao_builder=None):
        entidades = list(entidades or [])
        mapa_fretes = cls.mapear_fretes_por_codigos_ibge(
            banco=banco,
            codigos_ibge=[getattr(entidade, "enti_codi_cida", None) for entidade in entidades],
        )

        payloads = []
        for entidade in entidades:
            codigo_ibge = cls.normalizar_codigo_ibge(getattr(entidade, "enti_codi_cida", None))
            descricao = (
                descricao_builder(entidade)
                if callable(descricao_builder)
                else f"{entidade.enti_clie} - {entidade.enti_nome}"
            )
            payloads.append(
                cls.montar_payload_autocomplete(
                    entidade=entidade,
                    banco=banco,
                    text=descricao,
                    label=descricao,
                    frete_info=mapa_fretes.get(codigo_ibge) or {},
                )
            )
        return payloads
