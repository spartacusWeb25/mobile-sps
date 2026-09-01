# Trocas e Devoluções

> Gestão de trocas e devoluções a partir de pedidos de venda, em arquitetura horizontal.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `TrocasDevolucoes/` | `/api/{slug}/trocas-devolucoes/` | models · rest · services · Web |

## Visão geral

Documento próprio de troca/devolução referenciando o pedido de origem, com estrutura espelhada no app de Pedidos: views magras e lógica central em services. Campos seguem o padrão prefixo + 4 letras (`tdvl_*` cabeçalho, `itdv_*` itens). O desenho funcional completo (regras por domínio, fases do MVP) está no [mapeamento de trocas e devoluções](trocas-devolucoes-mapeamento.md).

## Modelos principais

| Modelo | Prefixo | Descrição |
| --- | --- | --- |
| Devolução (cabeçalho) | `tdvl_*` | Empresa/filial, pedido de origem (`tdvl_pdor`), cliente, vendedor, data, tipo (`tdvl_tipo`, ex.: `DEVO`), status (`tdvl_stat`), totais devolvido/reposto (`tdvl_tode`/`tdvl_tore`), saldo financeiro (`tdvl_safi`), observações |
| Item | `itdv_*` | Pedido/item de origem (`itdv_pdor`/`itdv_itor`), produto (`itdv_pror`), quantidade (`itdv_qtor`), valor (`itdv_vlor`), motivo (`itdv_moti`, ex.: `AVARIA`) |

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `devolucoes/` | Listagem — filtros: `tdvl_empr`, `tdvl_fili`, `tdvl_pdor`, `tdvl_stat` |
| `POST` | `devolucoes/` | Cria cabeçalho + array `itens` em um único payload |
| `GET` | `devolucoes/{tdvl_nume}/` | Detalhe |
| `PUT/PATCH` | `devolucoes/{tdvl_nume}/` | Atualização |

Exemplo de payload de criação:

```json
{
  "tdvl_empr": 1, "tdvl_fili": 1, "tdvl_pdor": 1024,
  "tdvl_clie": "1001", "tdvl_vend": "10", "tdvl_data": "2026-04-09",
  "tdvl_tipo": "DEVO", "tdvl_stat": "0",
  "tdvl_tode": "150.00", "tdvl_tore": "0.00", "tdvl_safi": "-150.00",
  "tdvl_obse": "Cliente devolveu por avaria",
  "itens": [
    { "itdv_pdor": 1024, "itdv_itor": 1, "itdv_pror": "PROD001",
      "itdv_qtor": "2.00000", "itdv_vlor": "150.00", "itdv_moti": "AVARIA" }
  ]
}
```

## Regras de negócio

- Toda troca/devolução referencia um pedido de origem; itens devolvidos não podem ultrapassar a quantidade líquida vendida.
- Processamento em sequência transacional: documento → estoque → financeiro → comissões → status/auditoria (detalhes no mapeamento).

## Integrações

- **Pedidos**: documento de origem e itens elegíveis.
- **Entradas/Saídas de Estoque**: retorno do item e nova saída (troca).
- **Financeiro**: estorno, crédito, abatimento ou diferença a cobrar.
- **Comissões**: estorno e recálculo.

---

*Padronizado em 2026-09-01. Fontes: `TrocasDevolucoes/README.md`, `TrocasDevolucoes/rest/README.md`.*
