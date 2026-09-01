# CFOP

> Cadastro de CFOPs com flags de incidência fiscal e API em formato agrupado para consumo do front.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `CFOP/` | `/api/{slug}/cfop/` | models · REST · services (MotorFiscal) |

## Visão geral

Além do cadastro de CFOPs (código, descrição, empresa), o app abriga as **flags de incidência** que orientam o cálculo fiscal (exige ICMS/IPI/PIS-COFINS/CBS/IBS, gera ST/DIFAL, composição de bases e totais) e o **MotorFiscal** — o orquestrador de cálculo de impostos usado pela emissão de notas (ver [Motor Fiscal](../arquitetura/motor-fiscal.md)).

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `/api/{slug}/cfop/` | Cadastro de CFOPs (rotas legadas equivalentes em `/cfop/cfop/`) |
| `GET` | `?q=<texto>` | Busca por código/descrição (icontains) |
| `GET` | `?select=1&q=<texto>` | Lista leve p/ autocomplete: `[{value, label}]`, máx. 20 |

### Contexto de empresa

O backend resolve a empresa nesta ordem: query param `empresa_id` → header `X-Empresa` → session → header `Empresa_id`. **O front deve sempre enviar `X-Empresa: <numero>`** (ou `?empresa_id=`). Em POST/PUT/PATCH, se o header vier, o backend força `cfop_empr` para esse valor.

### Formato de dados

As respostas agrupam os campos em duas listas, cada item com `campo`, `valor`, `label` e `help_text` (metadados para UI):

- `campos_padrao`: campos normais (`cfop_empr`, `cfop_codi`, `cfop_desc`, …);
- `incidencias`: flags booleanas (`cfop_exig_icms`, `cfop_exig_ipi`, `cfop_exig_pis_cofins`, `cfop_exig_cbs`, `cfop_exig_ibs`, `cfop_gera_st`, `cfop_gera_difal`, `cfop_icms_base_inclui_ipi`, `cfop_st_base_inclui_ipi`, `cfop_ipi_tota_nf`, `cfop_st_tota_nf`). Todas são sempre retornadas, mesmo quando `false`.

Criação/atualização aceita dois formatos: **agrupado** (mesma estrutura da resposta — recomendado para o front) ou **flat** (campos direto no JSON — útil para debug/integração). Flags aceitam boolean ou strings `"true"/"false"/"1"/"0"`.

## Regras de negócio

- As flags de incidência do CFOP são a fonte primária de decisão do MotorFiscal (o que calcular e como compor bases/totais).
- CFOP deve ter 4 dígitos (`cfop_codi`).

## Integrações

- **Notas Fiscais**: `CalculoImpostosService` consome o MotorFiscal e as flags do CFOP.
- **Produtos**: NCM + CFOP definem alíquotas via tabelas de mapeamento (`MapaCFOP`, `NCM_CFOP_DIF`).

---

*Padronizado em 2026-09-01. Fonte: `CFOP/REST/README.md`.*
