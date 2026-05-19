class MascaraGerencialService:

    @staticmethod
    def normalizar_niveis(valor):
        if isinstance(valor, list):
            return MascaraGerencialService.validar_niveis(valor)

        if isinstance(valor, str):
            partes = valor.replace(",", ".").split(".")
            partes = [p.strip() for p in partes if p.strip()]

            if not partes:
                raise ValueError("Informe a máscara.")

            niveis = []

            for index, digitos in enumerate(partes, start=1):
                niveis.append({
                    "nivel": index,
                    "digitos": int(digitos),
                    "tipo": "A" if index == len(partes) else "S",
                })

            return MascaraGerencialService.validar_niveis(niveis)

        raise ValueError("Máscara inválida.")

    @staticmethod
    def validar_niveis(niveis):
        if not isinstance(niveis, list) or not niveis:
            raise ValueError("Informe ao menos um nível para a máscara.")

        niveis_ordenados = sorted(niveis, key=lambda x: int(x["nivel"]))

        for index, item in enumerate(niveis_ordenados, start=1):
            item["nivel"] = int(item["nivel"])
            item["digitos"] = int(item["digitos"])
            item["tipo"] = item.get("tipo") or "S"

            if item["nivel"] != index:
                raise ValueError("Os níveis devem ser sequenciais começando em 1.")

            if item["digitos"] <= 0:
                raise ValueError("A quantidade de dígitos deve ser maior que zero.")

            if item["tipo"] not in ["S", "A"]:
                raise ValueError("O tipo deve ser S ou A.")

        niveis_ordenados[-1]["tipo"] = "A"

        return niveis_ordenados

    @staticmethod
    def gerar_exemplo(niveis):
        niveis = MascaraGerencialService.normalizar_niveis(niveis)
        return ".".join("1".zfill(int(item["digitos"])) for item in niveis)

    @staticmethod
    def get_tipo_por_nivel(niveis, nivel):
        niveis = MascaraGerencialService.normalizar_niveis(niveis)

        for item in niveis:
            if int(item["nivel"]) == int(nivel):
                return item["tipo"]

        raise ValueError("Nível não encontrado.")

    @staticmethod
    def get_digitos_por_nivel(niveis, nivel):
        niveis = MascaraGerencialService.normalizar_niveis(niveis)

        for item in niveis:
            if int(item["nivel"]) == int(nivel):
                return int(item["digitos"])

        raise ValueError("Nível não encontrado.")

    @staticmethod
    def total_niveis(niveis):
        return len(MascaraGerencialService.normalizar_niveis(niveis))