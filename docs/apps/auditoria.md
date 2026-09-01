# Auditoria

> Captura e registro de todas as alterações da aplicação — via API (middleware) e direto no banco (signals).

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `auditoria/` | `/api/{slug}/auditoria/` | models · middleware · signals · rest · utils · cron_jobs |

## Visão geral

Registra quem alterou o quê e quando, com estado **antes/depois** e lista dos campos alterados. A captura é dupla: o `AuditoriaMiddleware` intercepta requisições REST (com IP, navegador e payload) e os signals capturam alterações que não passam pela API (scripts, admin do Django).

## Modelos principais

| Modelo | Tabela | Descrição |
| --- | --- | --- |
| `LogAcao` | `auditoria_logacao` | Log: usuário, data/hora, tipo de ação (GET/POST/PUT/PATCH/DELETE), URL, IP, navegador, `dados`, `dados_antes`, `dados_depois`, `campos_alterados` (JSONB), objeto/modelo, empresa e licença |

`campos_alterados` tem o formato `{ "campo": { "antes": ..., "depois": ... } }`.

Índices: `(empresa, licenca, data_hora)`, `(usuario, data_hora)`, `(modelo, objeto_id)`, `(tipo_acao, data_hora)`.

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `logs/` | Logs da própria licença (usuários comuns) |
| `GET` | `logs/admin/` | Todos os logs (perfis `admin`, `supervisor`, `root`) |

Filtros: `data_inicio`, `data_fim`, `metodo`, `usuario`, `empresa`, `licenca`, `modelo`, `objeto_id`. Logs são somente leitura via API.

## Regras de negócio

- Campos sensíveis (`password`, `senha`, `token`, `api_key`, `secret`) são removidos automaticamente dos logs.
- Usuário comum só enxerga logs da própria licença.

## Configuração e operação

- Middlewares em `settings.py`: `auditoria.middleware.AuditoriaMiddleware` e `auditoria.signals.AuditoriaSignalMiddleware`.
- Limpeza: `python manage.py limpar_logs_auditoria --dias=365` (suporta `--dry-run`, `--licenca`, `--confirmar`).
- Relatórios: `python manage.py relatorio_auditoria --tipo=atividades|suspeitas|estatisticas|csv` (com filtros de data/usuário e saída CSV/JSON).
- Tarefas agendadas prontas em `auditoria.cron_jobs` (django-crontab ou Celery Beat): limpeza diária, relatório diário/semanal, detecção de atividades suspeitas a cada 4h e backup mensal.
- Alertas: `AUDITORIA_EMAIL_ALERTAS` no `settings.py`.
- Funções de análise em `auditoria.utils`: `gerar_relatorio_atividades`, `buscar_alteracoes_objeto`, `detectar_atividades_suspeitas`, `obter_estatisticas_rapidas`, `comparar_objetos_detalhado`.

## Pontos de atenção

- A tabela cresce rápido — manter a rotina de limpeza ativa (retenção sugerida: 1–2 anos).
- Em novos tenants, a tabela e os índices podem precisar ser criados via SQL (script no histórico do app).

---

*Padronizado em 2026-09-01. Fonte: `auditoria/README.md`.*
