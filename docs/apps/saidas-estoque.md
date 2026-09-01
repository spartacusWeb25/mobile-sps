# Saídas de Estoque

> Registro e consulta das saídas (baixas) de produtos do estoque, com verificação de saldo disponível.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Saidas_Estoque/` | `/api/{slug}/saidas-estoque/` | models · rest |

## Visão geral

Espelho das Entradas de Estoque para o sentido inverso: registra vendas, transferências e ajustes de baixa, com rastreabilidade de usuário e cliente.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `SaidasEstoque` | `saidasestoque` | `said_sequ` (PK sequencial) | Saída de produto |

Campos: `said_empr`/`said_fili`, `said_prod`, `said_enti` (cliente; nulo em transferências internas), `said_data`, `said_quan`, `said_tota`, `said_obse`, `said_usua`. Constraint de unicidade em `(empresa, filial, produto, data)`; ordenação padrão por data decrescente.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `saidas-estoque/` | Registro e consulta de saídas |
| `GET` | `saidas-estoque/resumo-por-produto/` | Resumo por produto no período |
| `GET` | `saidas-estoque/top-produtos/` | Produtos com maior saída |
| `GET` | `saidas-estoque/estoque-atual/` | Estoque atual do produto |

Filtros: `said_prod`, `said_enti` (`__isnull=true` para transferências), `said_data__range`, `said_tota__gte`.

## Regras de negócio

- Antes de registrar a saída, verificar estoque disponível (entradas − saídas ≥ quantidade).
- Quantidade e valor maiores que zero; data não pode ser futura.

## Integrações

- **Produtos**: valida produto e atualiza saldo.
- **Pedidos / CaixaDiario**: baixa automática por venda.
- **Entidades**: cliente da saída.
- **Auditoria**: log das operações.

---

*Padronizado em 2026-09-01. Fonte: `Saidas_Estoque/README.md`.*
