# Processos

> Processos com checklist configurável (tipos, modelos versionados, itens) — REST para mobile e web para administração.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `processos/` | `/api/{slug}/processos/` | models · services · rest · web |

## Visão geral

Permite definir **tipos de processo** (ex.: entrega técnica), montar **modelos de checklist** versionados com itens obrigatórios/opcionais, abrir processos que herdam o checklist ativo e registrar respostas até a validação final. A camada REST resolve o banco pelo `slug` (`core.utils.get_db_from_slug`), exige escopo de `empresa` e `filial` e repassa sempre `db_alias`/`empresa`/`filial` aos services — evitando vazamento entre tenants.

## Modelos principais

| Modelo | Descrição |
| --- | --- |
| `ProcessoTipo` | Tipo de processo (nome, código, ativo) |
| `ChecklistModelo` | Modelo de checklist vinculado a um tipo (versão, ativo) |
| `ChecklistItem` | Item do modelo (ordem, descrição, obrigatório) |
| `Processo` | Instância aberta de um tipo |
| `ProcessoChecklistResposta` | Resposta por item (`SIM`/`NAO`/`NA` + observação) |

## API

Headers obrigatórios (mobile): `Authorization: Bearer {token}`, `X-Empresa`, `X-Filial` e opcionalmente `X-Usuario` (auditoria sem sessão web).

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `tipos/` | Tipos de processo |
| `GET`/`POST` | `checklist-modelos/` | Modelos (vinculados a tipo ativo do mesmo escopo) |
| `GET`/`POST` | `checklist-itens/` | Itens (em modelo ativo do mesmo escopo) |
| `GET`/`POST` | `processos/` | Abertura gera respostas do checklist ativo |
| `GET` | `processos/{id}/checklist/` | Itens vinculados ao processo |
| `POST` | `processos/{id}/sincronizar-checklist/` | Vincula itens adicionados ao modelo após a abertura |
| `POST` | `processos/{id}/salvar-checklist/` | Salva respostas (aceita objeto por item ou lista `[{item_id, resposta, observacao}]`) |
| `POST` | `processos/{id}/validar/` | Valida obrigatórios → `APROVADO`/`REPROVADO` + `erros` |

## Fluxo recomendado no app mobile

1. Persistir `slug`, token, empresa, filial e usuário após o login.
2. `GET /tipos/` para o combo → `POST /processos/` para abrir.
3. `GET /processos/{id}/checklist/` para renderizar; `sincronizar-checklist` quando o modelo mudar.
4. Salvar incrementalmente; `validar` somente após confirmação/assinatura.

## Regras de negócio

- Abertura do processo copia o checklist **ativo** do tipo; itens criados depois só entram via sincronização explícita.
- Validação reprova se item obrigatório estiver marcado como `NAO` ou sem resposta.

## Pontos de atenção / melhorias sugeridas

- Padronizar a URL REST para evitar `processos/processos/` (ex.: `/instancias/`) numa versão futura.
- Adicionar paginação/filtros por status e tipo; persistir assinatura em campo próprio se precisar de validade histórica.

---

*Padronizado em 2026-09-01. Fonte: `docs/processos_rest_react_native.md`. Exemplo completo de client React Native: [guia de consumo React Native](processos-consumo-react-native.md).*
