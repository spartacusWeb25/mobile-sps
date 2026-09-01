# Caixa Diário

> Controle de caixa: abertura, fechamento, movimentações e fluxo de venda no PDV.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `CaixaDiario/` | `/api/{slug}/caixadiario/` | models · rest · web |

## Visão geral

Gerencia o caixa diário por operador e filial: abertura com registro de responsável, movimentações financeiras e fechamento com conferência de valores. Suporta múltiplos caixas por filial e o fluxo completo de venda no caixa (iniciar venda → adicionar itens → processar pagamento → finalizar).

## Modelos principais

| Modelo | Recurso | Descrição |
| --- | --- | --- |
| Caixa geral | `caixageral/` | Abertura/fechamento do caixa (por empresa/operador) |
| Movimentações | `movicaixa/` | Lançamentos financeiros do caixa |

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `caixageral/` | Controle de abertura/fechamento |
| CRUD | `movicaixa/` | Movimentações do caixa |
| `POST` | `movicaixa/iniciar_venda/` | Abre uma venda no caixa |
| `POST` | `movicaixa/adicionar_item/` | Adiciona um item à venda |
| `POST` | `movicaixa/adicionar_itens_lote/` | Adiciona itens em lote |
| `POST` | `movicaixa/processar_pagamento/` | Registra o pagamento |
| `POST` | `movicaixa/finalizar_venda/` | Conclui a venda |
| `GET` | `caixa/preco_produto/` | Preço do produto (aceita `promocional=1`, `opcoes=1`) |

## Regras de negócio

- Fluxo de venda é transacional: itens e pagamento vinculados à venda iniciada.
- Ao adicionar/atualizar item com preços promocionais, o front envia `preco_origem` e `preco_tipo` e o backend grava o unitário da tabela correspondente (ver [guia](precos-promocionais.md)).

## Integrações

- **Produtos**: consulta de preço (normal/promocional).
- **Saídas de Estoque**: baixa por venda à vista.
- **Contas a Receber / Financeiro**: registro dos recebimentos.

---

*Padronizado em 2026-09-01. Fonte: `CaixaDiario/README.md`.*
