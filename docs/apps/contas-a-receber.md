# Contas a Receber

> Títulos a receber: clientes, vencimentos, cobrança bancária, PIX e baixas (recebimentos).

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `contas_a_receber/` | `/api/{slug}/contas_a_receber/` | models · rest |

## Visão geral

Gestão completa do contas a receber: títulos por cliente, formas de recebimento, descontos por pontualidade, juros e multa por atraso, integração com cobrança bancária (nosso número/banco) e PIX (URL, TXID, EMV).

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `Titulosreceber` | — | Identificação lógica: empresa+filial+cliente+título+série+parcela | Título a receber |
| `Baretitulos` | — | `bare_sequ` | Baixa/recebimento do título |

Título: datas, valor, histórico, status `titu_aber` (`A` aberto / `B` baixado), descontos (`titu_desc_ao_dia`, `titu_desc_pont`), encargos (`titu_mult`, `titu_juro`), forma de recebimento (`titu_form_reci`), cobrança (`titu_noss_nume`, `titu_cobr_banc`) e PIX (`titu_url_pix`, `titu_txid_pix`, `titu_emv_pix`).

**Formas de recebimento** (`titu_form_reci`): `00` duplicata · `01` cheque · `02` promissória · `03` recibo · `50` cheque pré · `51` cartão crédito · `52` cartão débito · `53` boleto · `54` dinheiro · `55` depósito · `56` venda à vista · `60` PIX.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `titulos-receber/` | Por `{id}` ou pela chave composta completa (`{empr}/{fili}/{clie}/{titu}/{seri}/{parc}/{emis}/{venc}/`) |
| `POST` | `titulos-receber/{...}/baixar_titulo/` (ou `baixar/`) | Registra o recebimento |
| `DELETE` | `titulos-receber/{...}/excluir_baixa/` | Estorna a baixa |
| `GET` | `titulos-receber/{...}/historico_baixas/` | Histórico de recebimentos |
| `GET` | `titulos-receber/{id}/get_titulo_for_historico/` | Título com dados para histórico |

## Regras de negócio

- Na baixa: atraso aplica multa (% sobre o valor) e juros proporcionais (base mensal); pagamento pontual aplica `titu_desc_pont`; título passa a `titu_aber='B'`.
- Parcelamento segue o padrão título + parcela (`titu_parc` `001`, `002`, …).

## Integrações

- **Entidades**: cliente (`titu_clie`).
- **Pedidos**: geração de títulos por venda a prazo/à vista.
- **Boletos / EnvioCobranca**: emissão de boletos (Cora, Itaú, Sicredi) e cobrança; PIX gravado no próprio título.

---

*Padronizado em 2026-09-01. Fonte: `contas_a_receber/README.md`.*
