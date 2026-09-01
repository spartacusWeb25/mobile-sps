# Preços Promocionais

> Como o preço promocional (À vista / A prazo) funciona no Caixa, Pedidos e Orçamentos — web e REST.

## Visão geral

O sistema mantém tabela de preços **normal** e **promocional**. Nas telas de venda há um switch **"Usar preços promocionais"**; com ele ligado, ao selecionar um produto abre-se um modal com as duas opções (À vista / A prazo) e o valor escolhido é aplicado ao item. Integrado em Caixa, Pedidos e Orçamentos.

## Comportamento por tela (web)

| Tela | Template | Comportamento |
| --- | --- | --- |
| Caixa | `aba_produtos.html` | Switch ligado → chama `/web/{slug}/pedidos/preco/?prod_codi=...&pedi_fina=0&promocional=1&opcoes=1` e abre o modal com os dois preços. Ao adicionar/atualizar item (`venda_adicionar_item`, `venda_atualizar_item`), envia `preco_origem` e `preco_tipo`; o backend busca na tabela correspondente e grava o unitário correto |
| Pedidos | `pedidocriar.html` | No autocomplete do produto, com switch ligado busca `promocional=1&opcoes=1` e abre o modal antes de preencher o unitário |
| Orçamentos | `orcamentocriar.html` | Mesmo comportamento; aplica o valor em `iped_unit` |

## Parâmetros do endpoint de preço

`preco_produto` (Pedidos e Orçamentos web; também exposto via REST) aceita:

| Parâmetro | Efeito |
| --- | --- |
| `promocional=1` | Tenta usar a tabela promocional |
| `opcoes=1` | Retorna `prices.normal` e `prices.promocional`, cada um com `avista`/`prazo` |
| `modo=avista\|prazo` | Opcional; default segue `pedi_fina` do documento |

## Endpoints REST (mobile)

- Pedidos: `GET /api/{slug}/pedidos/preco-produto/?prod_codi=...&promocional=1&opcoes=1` (`PedidoVendaViewSet.preco_produto`)
- Caixa: `GET /api/{slug}/caixadiario/caixa/preco_produto/?prod_codi=...&promocional=1&opcoes=1` (`CaixaViewSet.preco_produto`)

## Regra de gravação

Ao adicionar/atualizar item, o front envia `preco_origem` (normal/promocional) e `preco_tipo` (à vista/a prazo); o backend respeita esses campos ao buscar o preço e gravar o unitário — nunca recalcula por conta própria.

---

*Padronizado em 2026-09-01. Fonte: `Produtos/servicos/readme_precos.md`.*
