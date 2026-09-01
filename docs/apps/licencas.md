# Licenças

> Usuários, empresas, filiais e licenciamento — autenticação, autorização, planos e trial do sistema.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Licencas/` (+ `planos/`, `licencas_web/`) | `/api/{slug}/licencas/` | models · rest · views |

## Visão geral

Núcleo de identidade e licenciamento. Controla usuários (autenticação customizada), empresas/filiais (por CNPJ), licenças com limite de empresas/filiais e módulos liberados. Trabalha em conjunto com os apps `planos` (planos e trial) e `licencas_web` (roteamento multi-tenant — ver [visão geral da arquitetura](../arquitetura/visao-geral.md)).

## Modelos principais

| Modelo | Banco | Chave | Descrição |
| --- | --- | --- | --- |
| `Usuarios` | tenant | `usua_codi` | Usuário (AbstractBaseUser; senha em `usua_senh_mobi`, setor em `usua_seto`) |
| `Empresas` | tenant | `empr_codi` | Empresa matriz (CNPJ único) |
| `Filiais` | tenant | `empr_empr` | Filial vinculada à empresa |
| `Licencas` | tenant | `lice_id` | Licença por CNPJ: bloqueio, limites, módulos (`get_modu_libe()`) |
| `Plano` | default | — | Tipo, preço, duração, status (`plan_ativ`, `plan_trial`, `plan_data_expi`) |
| `LicencaWeb` | default | — | Licença do cliente, vinculada a um `Plano`; slug + credenciais do banco |

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| `POST` | `licencas/login/` | Login (com verificação de plano/trial) |
| `POST` | `licencas/alterar-senha/` | Alteração de senha (`usuarioname`, `nova_senha`, `senha_atual` opcional; mínimo 4 caracteres) |
| CRUD | `usuarios/`, `empresas/`, `licencas/` | Cadastros |

## Regras de negócio

- **Autenticação**: `check_password` tenta hash Django primeiro, com fallback para texto plano (compatibilidade com legado).
- **Trial**: `PlanoService.criar_ambiente_trial()` gera slug incremental (`saveweb001`, …), cria `Plano` (15 dias, gratuito) e `LicencaWeb` no banco `default`, cria o banco PostgreSQL do tenant a partir do template `base_modelo`, popula empresa/filial/usuários `web` e `admin` e libera módulos via `PermissaoModulo`.
- **Bloqueio de trial expirado** (defesa em profundidade):
  1. Task Celery diária (`planos.tasks.verificar_trials_expirados`, 00:05) desativa planos vencidos e envia e-mail;
  2. No login, o plano é reverificado e desativado on-the-fly se o Celery atrasou; login retorna `403 {code: "trial_expirado"}`.
- Consultas a `Plano`/`LicencaWeb` devem usar `using('default')` explícito — o router de banco roteia pelo slug da URL e pode apontar para o banco do tenant, causando `DoesNotExist`.

## Integrações

- **Todos os apps**: autenticação, escopo empresa/filial e verificação de módulos liberados.
- **Celery**: workers/beat necessários em produção (`celery -A core worker` e `celery -A core beat`). Versões testadas: `celery==5.3.6`, `kombu==5.3.7`, `billiard==4.2.1` (as anteriores quebram com Python 3.12).

## Pontos de atenção

- Roadmap registrado: contrato de renovação ao expirar o trial (ClickSign), página web de renovação e webhook de pagamento para reativação automática.

---

*Padronizado em 2026-09-01. Fonte: `Licencas/README.md`.*
