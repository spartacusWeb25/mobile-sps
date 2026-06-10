from decimal import Decimal, ROUND_HALF_UP


class CobrancaOrigemService:
    @staticmethod
    def _to_money(valor) -> Decimal:
        try:
            return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal("0.00")

    @staticmethod
    def _to_date_iso(valor):
        if not valor:
            return None
        try:
            return valor.isoformat()
        except Exception:
            texto = str(valor or "").strip()
            return texto[:10] if texto else None

    @staticmethod
    def _to_int(valor, default=0):
        try:
            return int(Decimal(str(valor or default)))
        except Exception:
            return default

    @staticmethod
    def _sort_key(parcela):
        texto = str(parcela or "").strip()
        try:
            return (0, int(texto))
        except Exception:
            return (1, texto)

    @classmethod
    def _montar_saida(cls, *, numero_base, parcelas):
        parcelas = list(parcelas or [])
        if not parcelas:
            return {"fatura": None, "duplicatas": []}

        total = Decimal("0.00")
        duplicatas = []
        for idx, item in enumerate(parcelas, start=1):
            valor = cls._to_money(item.get("valor"))
            total += valor
            numero_dup = str(item.get("numero") or idx).strip() or str(idx)
            duplicatas.append(
                {
                    "ordem": cls._to_int(item.get("ordem"), idx),
                    "numero": numero_dup,
                    "data_vencimento": cls._to_date_iso(item.get("data_vencimento")),
                    "valor": valor,
                }
            )

        numero_fatura = str(numero_base or "").strip() or None
        return {
            "fatura": {
                "numero": numero_fatura,
                "valor_original": total,
                "valor_desconto": Decimal("0.00"),
                "valor_liquido": total,
            },
            "duplicatas": duplicatas,
        }

    @classmethod
    def from_pedido_pisos(cls, *, pedido, banco="default"):
        from contas_a_receber.models import Titulosreceber

        filtros = {
            "titu_empr": cls._to_int(getattr(pedido, "pedi_empr", 0)),
            "titu_fili": cls._to_int(getattr(pedido, "pedi_fili", 0)),
            "titu_clie": cls._to_int(getattr(pedido, "pedi_clie", 0)),
            "titu_titu": str(getattr(pedido, "pedi_nume", "") or "").strip()[:13],
        }
        if not filtros["titu_titu"]:
            return {"fatura": None, "duplicatas": []}

        qs = Titulosreceber.objects.using(banco).filter(**{**filtros, "titu_seri": "PVP"})
        if not qs.exists():
            qs = Titulosreceber.objects.using(banco).filter(**{**filtros, "titu_seri": "PIS"})

        titulos = sorted(list(qs), key=lambda t: cls._sort_key(getattr(t, "titu_parc", None)))
        parcelas = [
            {
                "ordem": idx,
                "numero": str(getattr(titulo, "titu_parc", "") or idx).strip() or str(idx),
                "data_vencimento": getattr(titulo, "titu_venc", None),
                "valor": getattr(titulo, "titu_valo", None),
            }
            for idx, titulo in enumerate(titulos, start=1)
        ]
        return cls._montar_saida(numero_base=getattr(pedido, "pedi_nume", None), parcelas=parcelas)

    @classmethod
    def from_pedido_venda(cls, *, pedido, banco="default"):
        from Pedidos.models import Parcelaspedidovenda
        from contas_a_receber.models import Titulosreceber

        parcelas_qs = Parcelaspedidovenda.objects.using(banco).filter(
            parc_empr=cls._to_int(getattr(pedido, "pedi_empr", 0)),
            parc_fili=cls._to_int(getattr(pedido, "pedi_fili", 0)),
            parc_pedi=cls._to_int(getattr(pedido, "pedi_nume", 0)),
        )
        parcelas_src = sorted(list(parcelas_qs), key=lambda p: cls._sort_key(getattr(p, "parc_parc", None)))
        if parcelas_src:
            parcelas = [
                {
                    "ordem": idx,
                    "numero": str(getattr(parcela, "parc_parc", "") or idx).strip() or str(idx),
                    "data_vencimento": getattr(parcela, "parc_venc", None),
                    "valor": getattr(parcela, "parc_valo", None),
                }
                for idx, parcela in enumerate(parcelas_src, start=1)
            ]
            return cls._montar_saida(numero_base=getattr(pedido, "pedi_nume", None), parcelas=parcelas)

        titulos_qs = Titulosreceber.objects.using(banco).filter(
            titu_empr=cls._to_int(getattr(pedido, "pedi_empr", 0)),
            titu_fili=cls._to_int(getattr(pedido, "pedi_fili", 0)),
            titu_clie=cls._to_int(getattr(pedido, "pedi_forn", 0)),
            titu_titu=str(getattr(pedido, "pedi_nume", "") or "").strip()[:13],
            titu_seri="PEV",
        )
        titulos = sorted(list(titulos_qs), key=lambda t: cls._sort_key(getattr(t, "titu_parc", None)))
        parcelas = [
            {
                "ordem": idx,
                "numero": str(getattr(titulo, "titu_parc", "") or idx).strip() or str(idx),
                "data_vencimento": getattr(titulo, "titu_venc", None),
                "valor": getattr(titulo, "titu_valo", None),
            }
            for idx, titulo in enumerate(titulos, start=1)
        ]
        return cls._montar_saida(numero_base=getattr(pedido, "pedi_nume", None), parcelas=parcelas)

    @classmethod
    def aplicar_no_payload(cls, *, payload, cobranca):
        payload = dict(payload or {})
        cobranca = cobranca or {}

        if cobranca.get("fatura") and not payload.get("fatura"):
            payload["fatura"] = cobranca["fatura"]
        if cobranca.get("duplicatas") and not payload.get("duplicatas"):
            payload["duplicatas"] = cobranca["duplicatas"]
        return payload
