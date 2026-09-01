# Orçamentos

> Propostas comerciais (orçamentos de venda) que podem ser transformadas em pedidos.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Orcamentos/` | `/api/{slug}/orcamentos/` | models · rest · web |

## Visão geral

Estrutura espelhada no app de Pedidos: cabeçalho + itens, com os mesmos prefixos de campo (`pedi_*`, `iped_*`). A principal ação específica é **transformar o orçamento em pedido**.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `Orcamentos` | — | `pedi_nume` (BigAuto) | Cabeçalho do orçamento |
| `ItensOrcamento` | — | empresa+filial+orçamento+item | Itens do orçamento |

Cabeçalho: empresa/filial, cliente (`pedi_forn`), vendedor (`pedi_vend`), data, total e observações (validade, condições de frete etc.). Itens: produto, quantidade, preço unitário/líquido, total, desconto (valor e %).

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `orcamentos/` | Por `{pedi_nume}` ou pela chave composta `{empresa}/{filial}/{numero}/` |
| `POST` | `orcamentos/{...}/transformar-em-pedido/` | Converte o orçamento em pedido de venda |
| `GET`/`PATCH` | `orcamentos/parametros-desconto/` | Parâmetros de desconto |

## Regras de negócio

- Total do orçamento = soma dos itens; recalcular após alterar itens.
- Suporta preços promocionais no mesmo fluxo dos Pedidos (switch + modal À vista/A prazo — ver [guia](precos-promocionais.md)).
- Limites de desconto controlados pelos parâmetros de desconto.

## Integrações

- **Pedidos**: conversão direta via `transformar-em-pedido`.
- **Entidades / Produtos**: cliente, vendedor e itens.
- **Pisos**: o vertical de pisos tem orçamento próprio (ver [app Pisos](pisos.md)).

---

*Padronizado em 2026-09-01. Fonte: `Orcamentos/README.md`.*
