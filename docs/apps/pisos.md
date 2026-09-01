# Pisos

> Vertical de vendas de pisos: produtos, orçamentos e pedidos próprios, com cálculo de metragem.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Pisos/` | `/api/{slug}/pisos/` | models · rest |

## Visão geral

Fluxo comercial específico para o segmento de pisos, paralelo ao fluxo padrão de Orçamentos/Pedidos: produtos com metragem, orçamento de pisos com itens e exportação para pedido.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `produtos-pisos/` | Produtos do vertical |
| `POST` | `produtos-pisos/calcular_metragem/` | Calcula metragem/caixas necessárias |
| CRUD | `orcamentos-pisos/` | Orçamentos (chave `orca_nume`) |
| `POST` | `orcamentos-pisos/{orca_nume}/exportar_pedido/` | Converte o orçamento em pedido |
| CRUD | `itens-orcamentos-pisos/` | Itens do orçamento |
| CRUD | `pedidos-pisos/` | Pedidos (chave `pedi_nume`) |
| CRUD | `itens-pedidos-pisos/` | Itens do pedido |

## Regras de negócio

- `calcular_metragem` converte área informada em quantidade de produto (caixas/peças) conforme o rendimento do piso.
- `exportar_pedido` é o caminho oficial do orçamento aprovado para o pedido.

## Integrações

- **Produtos / Pedidos / Orçamentos**: contrapartes do fluxo padrão.
- **Devoluções de Pisos** (`devolucoes_pisos/`): fluxo de devolução específico do vertical.

## Pontos de atenção

- O README original documenta apenas os endpoints; modelos e regras internas ainda precisam ser detalhados neste documento.

---

*Padronizado em 2026-09-01. Fonte: `Pisos/README.md`.*
