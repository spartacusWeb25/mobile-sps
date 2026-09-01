# Contas a Pagar

> Títulos a pagar: fornecedores, vencimentos, descontos, encargos e baixas (pagamentos).

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `contas_a_pagar/` | `/api/{slug}/contas_a_pagar/` | models · rest |

## Visão geral

Controla o ciclo do título a pagar, do lançamento (inclusive parcelado) à baixa, com suporte a descontos (à vista e pontualidade), multa e juros por atraso, pagamento eletrônico ao fornecedor, DDA/aprovação e campos de auditoria.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `Titulospagar` | — | Identificação lógica: empresa+filial+fornecedor+título+série+parcela | Título a pagar |
| `Bapatitulos` | — | `bapa_ctrl` | Baixa/pagamento do título |

Título: datas (`titu_emis`, `titu_venc`), valor, classificação contábil (conta, centro de custo, evento), status `titu_aber` (`A` aberto / baixado), descontos (`titu_desc_ao_dia`, `titu_desc_pont` — valor ou %), encargos (`titu_mult`, `titu_juro`, `titu_juro_mes`), dados de pagamento eletrônico (banco/agência/conta do fornecedor) e DDA. Baixa: data e valores pagos, multa/juros/desconto aplicados (valor e %), forma de pagamento, cheque, lotes e vínculos contábeis.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `titulos-pagar/` | Por `{id}` ou pela chave composta completa (`{empr}/{fili}/{forn}/{titu}/{seri}/{parc}/{emis}/{venc}/`) |
| `POST` | `titulos-pagar/{...}/baixar_titulo/` (ou `baixar/`) | Registra o pagamento |
| `DELETE` | `titulos-pagar/{...}/excluir_baixa/` | Estorna a baixa |
| `GET` | `titulos-pagar/{...}/historico_baixas/` | Histórico de pagamentos do título |

## Regras de negócio

- Vencimento não pode ser anterior à emissão; valor > 0; percentuais entre 0 e 100.
- Desconto (à vista/pontualidade) aplica-se a pagamento até o vencimento; multa fixa + juros proporcionais aos dias de atraso (base mensal) após o vencimento.
- Parcelamento: mesmo `titu_titu` com `titu_parc` sequencial (`001`, `002`, …) e vencimentos escalonados.
- Baixa atualiza o status do título (`titu_aber`).

## Integrações

- **Entidades**: fornecedor (`titu_forn`).
- **Plano de contas / Centro de custos**: classificação contábil do título.
- **Lançamentos bancários / boletos**: pagamento eletrônico e DDA.

## Pontos de atenção

- A rota por chave composta é longa e sensível à ordem dos segmentos — prefira a rota por `{id}` quando possível.

---

*Padronizado em 2026-09-01. Fonte: `contas_a_pagar/README.md`.*
