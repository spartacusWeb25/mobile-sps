# Lista de Casamento

> Listas de presentes de casamento: itens desejados, status de compra e conversão em pedidos.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `listacasamento/` | `/api/{slug}/listacasamento/` | models · rest |

## Visão geral

Permite criar listas de presentes vinculadas à noiva (Entidades), acompanhar o progresso de compra item a item e vincular itens finalizados a pedidos de venda.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `ListaCasamento` | `listacasamento` | `list_codi` (Auto) | Lista: nome, noiva (FK Entidades), data do evento, status, usuário responsável |
| `ItensListaCasamento` | `itenslistacasamento` | `item_item` | Item: produto, quantidade, finalizado (`item_fina`), pedido vinculado (`item_pedi`) |

**Status da lista** (`list_stat`): `0` Aberta · `1` Aguardando cliente · `2` Finalizada · `3` Cancelada.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `listas-casamento/` | Listas |
| CRUD | `itens-lista-casamento/` | Itens |
| `POST` | `itens-lista-casamento/update-lista/` | Atualização de itens em lote |

Filtros: `list_stat`, `list_data__gte`, `list_noiv`, `item_fina`.

## Regras de negócio

- Data do casamento não pode ser no passado; quantidade positiva; produto deve existir.
- Item comprado: `item_fina=True` + `item_pedi` com o número do pedido gerado.
- Progresso da lista = itens finalizados / total de itens.

## Integrações

- **Entidades**: noiva/cliente da lista.
- **Produtos**: catálogo dos itens.
- **Pedidos**: conversão do item em venda.

---

*Padronizado em 2026-09-01. Fonte: `listacasamento/README.md`.*
