# Entradas de Estoque

> Registro e consulta das entradas de produtos no estoque, com histórico por empresa/filial.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Entradas_Estoque/` | `/api/{slug}/entradas-estoque/` | models · rest |

## Visão geral

Registra toda entrada de mercadoria no estoque (compras, devoluções de clientes, ajustes), mantendo histórico completo segregado por empresa e filial.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `EntradaEstoque` | `entradasestoque` | `entr_sequ` (PK sequencial) | Entrada de produto |

Campos: `entr_empr`/`entr_fili`, `entr_prod` (produto), `entr_enti` (fornecedor), `entr_data`, `entr_quan`, `entr_tota`, `entr_obse`, `entr_usua` (usuário responsável). Constraint de unicidade em `(empresa, filial, produto, data)`.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `entradas-estoque/` | Registro e consulta de entradas |

Filtros: `entr_prod`, `entr_enti`, `entr_data__gte` / `entr_data__range`, `entr_tota__gte`.

## Regras de negócio

- Quantidade e valor total devem ser maiores que zero; data não pode ser futura.
- Produto e fornecedor devem existir nos cadastros.
- O saldo atual do produto (`SaldoProduto`) é derivado de entradas − saídas.

## Integrações

- **Produtos**: valida `prod_codi` e alimenta saldo/custo médio.
- **Entidades**: fornecedor da entrada.
- **Auditoria**: log das operações.

## Pontos de atenção

- A constraint `(empresa, filial, produto, data)` impede duas entradas do mesmo produto no mesmo dia — agrupe quantidades quando necessário.

---

*Padronizado em 2026-09-01. Fonte: `Entradas_Estoque/README.md`.*
