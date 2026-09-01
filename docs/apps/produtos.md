# Produtos

> Cadastro de produtos com categorização, tabela de preços, saldos de estoque e histórico de alterações.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Produtos/` | `/api/{slug}/produtos/` | models · rest (views/serializers) · consultas · servicos · regras · utils |

## Visão geral

Gerencia o catálogo de produtos e tudo que orbita em torno dele: hierarquia (grupos, subgrupos, famílias, marcas), unidades de medida, NCM, código de barras, foto, preços por empresa/filial e saldo de estoque por filial. O app segue estrutura horizontal com pastas separadas para `views`, `consultas`, `servicos`, `regras` e `utils`.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `Produtos` | `produtos` (managed=False) | `prod_codi` (PK) | Cadastro do produto |
| `Tabelaprecos` | `tabelaprecos` | empresa+filial+produto | Preços, custos e impostos |
| `Tabelaprecoshist` | — | — | Histórico de alterações de preço |
| `SaldoProduto` | `saldosprodutos` | produto+empresa+filial | Saldo de estoque |
| `GrupoProduto`, `FamiliaProduto`, `Marca`, `UnidadeMedida` | `gruposprodutos`, … | — | Classificação |

Preços em `Tabelaprecos`: base (`tabe_prco`), à vista (`tabe_avis`), a prazo (`tabe_apra`), varejo (`tabe_vare`), custos (`tabe_cust`, `tabe_cuge`), impostos (ICMS, IPI, ST), margem, frete e despesas.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `produtos/` | Cadastro de produtos |
| CRUD | `grupos/` | Grupos de produtos |
| CRUD | `precos/` | Tabela de preços |
| `GET` | `saldos/` e `saldos/{produto}/` | Saldos de estoque |

Filtros: produtos por `prod_empr`, `prod_grup`, `prod_marc`, `prod_nome`, `search`; preços por `tabe_empr`, `tabe_fili`, `tabe_prod`, `preco_min`, `preco_max`.

## Regras de negócio

- Preço é definido por **empresa + filial + produto** (chave composta) — usar `update_or_create` para evitar duplicatas.
- **Preços promocionais**: tabelas normal e promocional convivem; ver [guia de preços promocionais](precos-promocionais.md) para o fluxo no Caixa/Pedidos/Orçamentos.
- Existe a view `produtos_detalhados` no banco, que junta produto + grupo + marca + preço + saldo (usada em listagens e cálculo de valor de estoque).

## Integrações

- **Pedidos / Orçamentos / Caixa**: itens referenciam `prod_codi`; consulta de preço por tipo financeiro.
- **Entradas/Saídas de Estoque**: movimentam o saldo do produto.
- **Notas Fiscais / CFOP**: NCM do produto participa do cálculo fiscal.

## Pontos de atenção

- `prod_foto` é `BinaryField` — exige conversão para exibição.
- Tabelas não gerenciadas pelo Django; a view `produtos_detalhados` precisa ser criada manualmente no banco de novos tenants.

---

*Padronizado em 2026-09-01. Fonte: `Produtos/README.md`.*
