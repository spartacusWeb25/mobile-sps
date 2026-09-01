# Fluxo de Emissão de NF-e

> Caminho completo da emissão: modelos → cálculo → DTO → XML PyNFe → assinatura A1 → SEFAZ → retorno.

## Diagrama do fluxo

```mermaid
graph TD
    classDef model fill:#e1f5fe,stroke:#01579b,color:#01579b
    classDef service fill:#fff3e0,stroke:#e65100,color:#e65100
    classDef dto fill:#f3e5f5,stroke:#4a148c,color:#4a148c
    classDef adapter fill:#e8f5e9,stroke:#1b5e20,color:#1b5e20
    classDef sefaz fill:#263238,stroke:#000,color:#fff

    subgraph Dados [1. Persistência]
        DB[(PostgreSQL)]:::model
        Models["models.py (Nota, NotaItem)"]:::model
        DB <--> Models
    end

    subgraph Servico [2. Regras de negócio]
        CalcService["calculo_impostos_service.py"]:::service
        NotaService["nota_service.py (orquestrador)"]:::service
        Models --> NotaService
        NotaService --> CalcService
        CalcService -->|atualiza impostos| Models
    end

    subgraph Dominio [3. Transformação]
        Builder["dominio/builder.py (NotaBuilder)"]:::dto
        DTO["dominio/dto.py (NotaFiscalDTO)"]:::dto
        NotaService --> Builder
        Builder -->|lê| Models
        Builder -->|gera| DTO
    end

    subgraph Aplicacao [4. Construção do XML]
        PyNFeBuilder["aplicacao/construir_nfe_pynfe.py"]:::adapter
        PyNFeObj["Objeto PyNFe (NotaFiscal)"]:::adapter
        ExtraData["lista _itens_extra (IBS/CBS)"]:::adapter
        DTO --> PyNFeBuilder --> PyNFeObj
        PyNFeBuilder -.-> ExtraData
    end

    subgraph Infra [5. Comunicação SEFAZ]
        SefazAdapter["infrastructure/sefaz_adapter.py"]:::adapter
        SEFAZ((SEFAZ)):::sefaz
        PyNFeObj -->|serializa| SefazAdapter
        ExtraData -->|injeção manual| SefazAdapter
        SefazAdapter -->|assina e envia SOAP| SEFAZ
    end

    SEFAZ -->|XML retorno| SefazAdapter
    SefazAdapter -->|status/motivo| NotaService
    NotaService -->|chave/protocolo| Models
```

## Responsabilidade de cada arquivo

| Etapa | Arquivo | Função |
| --- | --- | --- |
| 1 | `Notas_Fiscais/models.py` | `Nota`, `NotaItem`, `NotaItemImposto` (inclui IBS/CBS) |
| 2 | `services/calculo_impostos_service.py` | Cálculo tributário pré-emissão; alíquotas IBS/CBS; regras defensivas (ex.: `cst_icms` nunca nulo) |
| 3 | `dominio/builder.py` | Padrão *Builder*: modelos Django → DTO plano. Desacopla emissão do esquema do banco |
| 3 | `dominio/dto.py` | `NotaFiscalDTO`: emitente, destinatário, itens, `valor_ibs`/`valor_cbs` etc. |
| 4 | `aplicacao/construir_nfe_pynfe.py` | DTO → objetos PyNFe. Campos IBS/CBS ficam na lista `_itens_extra` ("pegam carona" até a assinatura) |
| 5 | `infrastructure/sefaz_adapter.py` | Serializa o XML, **injeta manualmente** as tags `<IBS>`/`<CBS>` (só quando valores > 0 — evita erro 225), assina com certificado A1, transmite via SOAP e loga o retorno (diagnóstico de erros como 656/225) |
| 6 | `services/nota_service.py` | Orquestra tudo e atualiza o status da nota (autorizada/rejeitada/cancelada) |

## Pendências conhecidas

- Campos `id_csrt` e `hash_csrt` faltam no `ResponsavelTecnicoDTO` — obter dos dados da filial ou dos XMLs emitidos pelo Spartacus.

---

*Padronizado em 2026-09-01. Fonte: `Notas_Fiscais/ESTRUTURA_EMISSAO.md` (movido para docs).*
