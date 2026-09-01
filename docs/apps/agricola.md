# Agrícola

> Módulo agrícola: controle de estoque por fazenda, rastreabilidade por lotes e parametrização sincronizada entre empresas.

| Localização | Camadas |
| --- | --- |
| `Agricola/` | models · registry · service · web |

## Visão geral

Este documento descreve as decisões de modelagem e a estrutura de parametrização do módulo agrícola, bem como o processo de sincronização entre empresas em ambiente multi-tenant.

## Modelagem de estoque e lotes

### Controle de estoque global

A tabela `EstoqueFazenda` mantém o controle consolidado do estoque por empresa, filial, fazenda e produto.

| Item | Valor |
| --- | --- |
| Model | `EstoqueFazenda` |
| Campos-chave | `estq_empr`, `estq_fili`, `estq_faze`, `estq_prod` |
| Saldo | `estq_quant` |

### Controle de lotes

Para produtos que exigem rastreabilidade detalhada (defensivos, sementes), utiliza-se a tabela `LoteProdutos`.

| Item | Valor |
| --- | --- |
| Model | `LoteProdutos` |
| Tabela | `produtos_lotes` |
| Campo de quantidade | `lote_quant` (validado como o campo correto para saldo de lote, em detrimento de `lote_quan`) |

Um produto pode ter múltiplos lotes. O somatório de `lote_quant` deve ser conciliado com `EstoqueFazenda.estq_quant` quando o parâmetro `controla_lote` estiver ativo.

## Parametrização

Os parâmetros agrícolas são definidos em `Agricola.registry.ParametrosAgricolasRegistry`. Os valores são armazenados na tabela `ParametroAgricola`, mas as definições (tipo, default, label) ficam no código (registry).

Exemplos de parâmetros:

| Parâmetro | Tipo | Efeito |
| --- | --- | --- |
| `controla_estoque` | bool | Ativa/desativa validações de estoque |
| `permite_estoque_negativo` | bool | Permite saídas sem saldo suficiente |
| `controla_lote` | bool | Exige identificação de lote nas movimentações |

O `ParametroAgricolaService` (`Agricola.service.parametros`) é responsável por ler e escrever os parâmetros, utilizando cache ou consulta direta ao banco.

## Sincronização multi-empresa

Em ambiente multi-tenant, a sincronização garante que novos parâmetros definidos no registry sejam criados em todos os bancos configurados. O comando `sync_parametros_agricola`:

1. Carrega todas as licenças ativas via `core.licencas_loader.carregar_licencas_dict`;
2. Itera sobre cada banco de dados configurado;
3. Garante a existência dos registros de parâmetros para todas as empresas/filiais daquele banco.

Isso elimina a execução manual do comando para cada banco individualmente.

## Manutenção

### Adicionar novo parâmetro

1. Edite `Agricola/registry.py` e adicione a chave no dicionário `PARAMS`:

   ```python
   "novo_parametro": {
       "tipo": bool,
       "default": False,
       "label": "Novo Parâmetro",
       "grupo": "Geral"
   }
   ```

2. Execute a sincronização:

   ```bash
   python manage.py sync_parametros_agricola
   ```

### Layout do painel

O painel de parâmetros (`parametros_agricolas.html`) segue o padrão visual do painel de módulos, utilizando Tailwind/CSS customizado para modo escuro (`#0f1419`).

---

*Padronizado em 2026-09-01. Fonte: `docs/agricola_parametros_guide.md` (movido para docs/apps/).*
