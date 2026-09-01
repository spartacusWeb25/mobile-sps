# Pedidos

> Pedidos de venda: cabeçalho, itens, ciclo de status e integração com financeiro, estoque e comissões.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Pedidos/` | `/api/{slug}/pedidos/` | models · rest · services · web |

## Visão geral

Gerencia o ciclo completo do pedido de venda. O app é a referência da **arquitetura horizontal** do projeto (ver [visão geral da arquitetura](../arquitetura/visao-geral.md)): views magras, regras de negócio em `services/`, contratos em `serializers`.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `PedidoVenda` | `pedidosvenda` (managed=False) | `pedi_nume` (BigAuto) | Cabeçalho do pedido |
| `Itenspedidovenda` | `itenspedidovenda` | empresa+filial+pedido+item | Itens do pedido |

Cabeçalho: cliente (`pedi_forn` → `enti_clie`), vendedor (`pedi_vend`), data, total (`pedi_tota`), tipo financeiro (`pedi_fina`), status (`pedi_stat`), cancelado (`pedi_canc`), observações. Itens: produto, unidade, quantidade, preço unitário/líquido, total, desconto (valor e %), custo, frete e vendedor.

**Status** (`pedi_stat`): `0` Pendente · `1` Processando · `2` Enviado · `3` Concluído · `4` Cancelado (com `pedi_canc=True`).

**Tipo financeiro** (`pedi_fina`): `0` À vista · `1` A prazo · `2` Sem financeiro.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `pedidos/` | Cabeçalho do pedido |
| CRUD | `itens/` | Itens do pedido |
| `GET` | `preco-produto/` | Preço do produto (aceita `promocional=1`, `opcoes=1`, `modo=avista\|prazo`) |

Filtros de pedidos: `pedi_empr`, `pedi_fili`, `pedi_forn`, `pedi_vend`, `pedi_stat`, `pedi_fina`, `pedi_data` (range), `pedi_canc`, `search`. Itens: `iped_pedi`, `iped_prod`, `iped_vend`.

## Regras de negócio

- O total do pedido (`pedi_tota`) é a soma dos `iped_tota` dos itens — recalcular após alterar itens.
- Pedido cancelado deve ter `pedi_stat='4'` e `pedi_canc=True`.
- Pedido a prazo gera parcelas em Contas a Receber; à vista gera título único.
- Existe a view `pedidos_geral` no banco, que consolida pedido + cliente + vendedor + itens agregados (nomes de produtos, quantidade total, tipo financeiro descrito).

## Integrações

- **Entidades**: cliente e vendedor por código de entidade.
- **Produtos**: itens e consulta de preço (normal/promocional).
- **Contas a Receber**: geração de títulos conforme tipo financeiro.
- **Saídas de Estoque**: baixa dos itens vendidos.
- **Comissões**: cálculo sobre o total do pedido/itens.
- **Trocas e Devoluções**: pedido é o documento de origem (ver [app TrocasDevolucoes](trocas-devolucoes.md)).

## Pontos de atenção

- `iped_pedi` é `CharField` — o vínculo item→pedido é textual, sem FK física.
- A view `pedidos_geral` precisa ser criada manualmente em novos tenants.

---

*Padronizado em 2026-09-01. Fonte: `Pedidos/README.md`.*
