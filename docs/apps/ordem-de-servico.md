# Ordem de Serviço

> Ordens de serviço com peças, serviços, imagens georreferenciadas, workflow por setor e faturamento.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `OrdemdeServico/` | `/api/{slug}/ordemdeservico/` | models · rest · services · web |

## Visão geral

Gerencia OS completas para manutenção/assistência técnica: abertura, orçamento, liberação, execução e finalização, com prioridade, setorização (workflow entre setores), documentação fotográfica em três momentos (antes/durante/depois, com geolocalização) e geração de títulos financeiros.

Arquitetura interna em camadas: **Domínio** decide o que pode · **Service** executa o fluxo · **Repository** fala com o banco · **View** entrega HTTP · **Handler** traduz erro.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `Ordemservico` | `ordemservico` | `orde_nume` | Cabeçalho da OS |
| `Ordemservicopecas` | — | — | Peças aplicadas (`peca_*`) |
| Serviços | — | — | Serviços executados |
| Imagens | `ordemservicoimgantes/durante/depois` | `iman_id`/`imdu_id`/`imde_id` | Fotos com comentário, lat/long e timestamp |
| Workflow | — | `wkfl_id` / `osfs_codi` | Setores e fases do fluxo |

**Status** (`orde_stat_orde`): `0` Aberta · `1` Orçamento gerado · `2` Aguardando liberação · `3` Liberada · `4` Finalizada · `5` Reprovada · `20` Faturada parcial.
**Prioridade** (`orde_prio`): `normal` · `alerta` · `urgente`.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `ordens/` | Ordens de serviço |
| `POST` | `ordens/{id}/atualizar_total/` | Recalcula o total (peças + serviços) |
| `POST` | `ordens/{id}/avancar-setor/` | Avança a OS no workflow |
| `GET` | `ordens/{id}/proximos-setores/` | Setores disponíveis |
| `GET` | `ordens/{id}/historico-workflow/` | Histórico de movimentações |
| CRUD | `pecas/`, `servicos/` | Itens da OS (+ `update-lista/` para atualização em lote) |
| CRUD | `imagens-antes/`, `imagens-durante/`, `imagens-depois/` | Documentação fotográfica |
| CRUD | `workflow-setor/`, `fase-setor/` | Configuração do workflow |
| `POST` | `financeiro/gerar-titulos/` | Fatura a OS (gera títulos) |
| `GET` | `financeiro/consultar-titulos/{orde_nume}/` | Títulos da OS |
| `POST` | `financeiro/remover-titulos/` | Remove títulos gerados |
| `GET` | `financeiro/relatorio/` | Relatório financeiro de OS |

Filtros de ordens: `orde_stat_orde`, `orde_prio`, `orde_enti`, `orde_data_aber__gte`.

## Regras de negócio

- Total da OS = soma de peças + serviços (`calcular_total()` / `atualizar_total`).
- Workflow por setor controla quem pode avançar a OS e mantém trilha de histórico.
- Faturamento integra com Contas a Receber, incluindo faturamento parcial (status `20`).

## Integrações

- **Entidades**: cliente da OS (`orde_enti`).
- **Produtos**: peças aplicadas.
- **Contas a Receber**: títulos gerados no faturamento.
- **Licencas**: setorização por usuário (`usua_seto`).

## Pontos de atenção

- Imagens são `BYTEA` no banco (3 tabelas separadas por momento) com colunas de geolocalização adicionadas por migração idempotente.

---

*Padronizado em 2026-09-01. Fonte: `OrdemdeServico/README.md`.*
