# NFS-e

> Notas fiscais de serviço eletrônicas (módulo em estruturação).

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `nfse/` | — | models · REST · WEB |

## Visão geral

Módulo de NFS-e com a estrutura padrão do projeto já criada:

```text
nfse/
    models.py
    REST/   (serializers.py, views.py, api_urls.py)
    WEB/    (forms.py, views.py, web_urls.py)
```

## Pontos de atenção

- Documentação mínima — o README original registra apenas a estrutura de pastas. Completar este documento (modelos, endpoints, prefeituras suportadas) conforme o módulo evoluir, seguindo o [template](../TEMPLATE.md).

---

*Padronizado em 2026-09-01. Fonte: `nfse/readme.md`.*
