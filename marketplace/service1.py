class MercadoLivreAtributoTraducaoService:

    TRADUCOES_FIXAS = {
        "GTIN": "Código de barras",
        "BRAND": "Marca",
        "MODEL": "Modelo",
        "COLOR": "Cor",
        "SIZE": "Tamanho",
        "SIZE_GRID_ID": "Tabela de medidas",
        "GENDER": "Gênero",
        "AGE_GROUP": "Faixa etária",
        "LINE": "Linha",
        "MATERIAL": "Material",
        "WEIGHT": "Peso",
        "HEIGHT": "Altura",
        "WIDTH": "Largura",
        "LENGTH": "Comprimento",
        "VOLTAGE": "Voltagem",
        "POWER": "Potência",
    }

    @classmethod
    def obter_ou_criar_traducao(cls, attr, category_id=None):
        attr_id = attr.get("id")
        nome_original = attr.get("name")

        if not attr_id:
            return ""

        nome_sugerido = (
            cls.TRADUCOES_FIXAS.get(attr_id)
            or cls.humanizar_nome(nome_original)
            or cls.humanizar_id(attr_id)
        )

        obj, created = MercadoLivreAtributoTraducao.objects.update_or_create(
            attr_id=attr_id,
            defaults={
                "nome_original": nome_original,
                "value_type": attr.get("value_type"),
                "ultima_categoria_id": category_id,
                "nome_pt": nome_sugerido,
            }
        )

        return obj.nome_pt or nome_sugerido

    @staticmethod
    def humanizar_id(attr_id):
        return attr_id.replace("_", " ").title() if attr_id else ""

    @staticmethod
    def humanizar_nome(nome):
        if not nome:
            return ""

        mapa = {
            "Brand": "Marca",
            "Model": "Modelo",
            "Color": "Cor",
            "Size": "Tamanho",
            "Weight": "Peso",
            "Height": "Altura",
            "Width": "Largura",
            "Length": "Comprimento",
            "Power": "Potência",
            "Voltage": "Voltagem",
            "Capacity": "Capacidade",
            "Storage": "Armazenamento",
            "Screen": "Tela",
            "Battery": "Bateria",
            "Material": "Material",
            "Type": "Tipo",
            "Line": "Linha",
            "Package": "Embalagem",
        }

        texto = nome

        for en, pt in mapa.items():
            texto = texto.replace(en, pt)

        return texto