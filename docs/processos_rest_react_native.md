# Processos — versão REST e consumo React Native

## Verificação arquitetural

O app `processos` segue a arquitetura horizontal esperada:

- `processos/models.py`: modelos ORM (`ProcessoTipo`, `ChecklistModelo`, `ChecklistItem`, `Processo`, `ProcessoChecklistResposta`).
- `processos/services/`: regras de negócio e persistência roteada por `db_alias`, `empresa` e `filial`.
- `processos/rest/`: contratos REST/DTOs, roteador e viewsets para consumo mobile.
- `processos/web/`: formulários e views Django Templates para operação administrativa e fluxo de checklist.

A camada REST resolve o banco pelo `slug` com `core.utils.get_db_from_slug`, exige escopo de `empresa` e `filial`, e repassa sempre `db_alias`, `empresa` e `filial` para os services. Isso evita vazamento entre bancos, empresas e filiais.

## Base URL

As rotas são montadas pelo roteador global em:

```txt
/api/{slug}/processos/
```

Exemplo:

```txt
/api/save1/processos/processos/
```

## Headers obrigatórios para React Native

Quando o usuário já selecionou empresa e filial, o app mobile deve enviar:

```http
Authorization: Bearer {accessToken}
Content-Type: application/json
X-Empresa: 1
X-Filial: 1
X-Usuario: 123
```

`X-Usuario` é opcional e usado para auditoria de abertura/validação quando a sessão web não existe.

## Endpoints

### Tipos de processo

| Método | Rota | Uso |
| --- | --- | --- |
| `GET` | `/api/{slug}/processos/tipos/` | Lista tipos no escopo empresa/filial. |
| `POST` | `/api/{slug}/processos/tipos/` | Cria tipo. |
| `GET` | `/api/{slug}/processos/tipos/{id}/` | Detalha tipo. |
| `PUT/PATCH` | `/api/{slug}/processos/tipos/{id}/` | Atualiza tipo. |

Payload de criação:

```json
{
  "nome": "Entrega técnica",
  "codigo": "ENT_TEC",
  "ativo": true
}
```

### Modelos de checklist

| Método | Rota | Uso |
| --- | --- | --- |
| `GET` | `/api/{slug}/processos/checklist-modelos/` | Lista modelos no escopo. |
| `POST` | `/api/{slug}/processos/checklist-modelos/` | Cria modelo vinculado a tipo ativo da mesma empresa/filial. |

Payload:

```json
{
  "processo_tipo_id": 10,
  "nome": "Checklist padrão",
  "versao": 1,
  "ativo": true
}
```

### Itens de checklist

| Método | Rota | Uso |
| --- | --- | --- |
| `GET` | `/api/{slug}/processos/checklist-itens/` | Lista itens no escopo. |
| `POST` | `/api/{slug}/processos/checklist-itens/` | Cria item em modelo ativo da mesma empresa/filial. |

Payload:

```json
{
  "checklist_modelo_id": 7,
  "ordem": 1,
  "descricao": "Documento conferido",
  "obrigatorio": true
}
```

### Processos

| Método | Rota | Uso |
| --- | --- | --- |
| `GET` | `/api/{slug}/processos/processos/` | Lista processos com tipo e respostas. |
| `POST` | `/api/{slug}/processos/processos/` | Abre processo e gera respostas do checklist ativo. |
| `GET` | `/api/{slug}/processos/processos/{id}/` | Detalha processo. |
| `GET` | `/api/{slug}/processos/processos/{id}/checklist/` | Retorna os itens já vinculados ao processo. |
| `POST` | `/api/{slug}/processos/processos/{id}/sincronizar-checklist/` | Vincula ao processo os itens adicionados posteriormente ao modelo ativo. |
| `POST` | `/api/{slug}/processos/processos/{id}/salvar-checklist/` | Salva respostas. |
| `POST` | `/api/{slug}/processos/processos/{id}/validar/` | Valida obrigatórios e aprova/reprova processo. |

Criar processo:

```json
{
  "tipo_id": 10,
  "descricao": "Processo aberto pelo app mobile"
}
```


Sincronizar itens novos do modelo ativo com um processo já aberto:

```json
{
  "ok": true,
  "criadas": 2,
  "modelo_id": 7,
  "respostas": []
}
```

Salvar checklist com objeto por item:

```json
{
  "respostas": {
    "101": {"resposta": "SIM", "observacao": "OK"},
    "102": {"resposta": "NAO", "observacao": "Faltou assinatura"},
    "103": {"resposta": "NA", "observacao": "Não aplicável"}
  }
}
```

Salvar checklist com lista (formato mais natural no React Native):

```json
{
  "respostas": [
    {"item_id": 101, "resposta": "SIM", "observacao": "OK"},
    {"item_id": 102, "resposta": "NAO", "observacao": "Faltou assinatura"},
    {"item_id": 103, "resposta": "NA", "observacao": "Não aplicável"}
  ]
}
```

Resposta de validação:

```json
{
  "aprovado": false,
  "status": "REPROVADO",
  "erros": ["Item obrigatório marcado como NÃO: Documento conferido"]
}
```

## Exemplo de client React Native

```ts
const API_URL = 'https://seu-dominio.com/api';

type Scope = {
  slug: string;
  empresa: number;
  filial: number;
  usuarioId?: number;
  token: string;
};

function processosHeaders(scope: Scope) {
  return {
    Authorization: `Bearer ${scope.token}`,
    'Content-Type': 'application/json',
    'X-Empresa': String(scope.empresa),
    'X-Filial': String(scope.filial),
    ...(scope.usuarioId ? {'X-Usuario': String(scope.usuarioId)} : {}),
  };
}

export async function listarProcessos(scope: Scope) {
  const response = await fetch(`${API_URL}/${scope.slug}/processos/processos/`, {
    method: 'GET',
    headers: processosHeaders(scope),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function criarProcesso(scope: Scope, tipoId: number, descricao: string) {
  const response = await fetch(`${API_URL}/${scope.slug}/processos/processos/`, {
    method: 'POST',
    headers: processosHeaders(scope),
    body: JSON.stringify({tipo_id: tipoId, descricao}),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function sincronizarChecklist(scope: Scope, processoId: number) {
  const response = await fetch(`${API_URL}/${scope.slug}/processos/processos/${processoId}/sincronizar-checklist/`, {
    method: 'POST',
    headers: processosHeaders(scope),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function salvarChecklist(scope: Scope, processoId: number, respostas: Array<unknown>) {
  const response = await fetch(`${API_URL}/${scope.slug}/processos/processos/${processoId}/salvar-checklist/`, {
    method: 'POST',
    headers: processosHeaders(scope),
    body: JSON.stringify({respostas}),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function validarProcesso(scope: Scope, processoId: number) {
  const response = await fetch(`${API_URL}/${scope.slug}/processos/processos/${processoId}/validar/`, {
    method: 'POST',
    headers: processosHeaders(scope),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
```

## Dinâmica recomendada no app mobile

1. Após login, persistir `slug`, `token`, `empresa`, `filial` e `usuarioId` no estado seguro do app.
2. Carregar `GET /tipos/` para preencher o combo de tipo.
3. Criar processo em `POST /processos/`.
4. Abrir o detalhe e chamar `GET /processos/{id}/checklist/` para renderizar a lista de perguntas já vinculadas.
5. Quando o backend informar/usuário solicitar atualização do template, chamar `POST /processos/{id}/sincronizar-checklist/` para adicionar itens criados depois da abertura.
6. Salvar incrementalmente em `POST /processos/{id}/salvar-checklist/`.
7. Chamar `POST /processos/{id}/validar/` apenas após assinatura/confirmacão no app.
8. Tratar `status = APROVADO` como fluxo finalizado e `REPROVADO` exibindo `erros` para correção.

## Observações sobre o front Django

O fluxo web está coerente: cadastro de templates, abertura de processo, detalhe com itens já vinculados, sincronização explícita de itens adicionados posteriormente ao template, salvamento das respostas e validação com assinatura. A tela de templates passou a exibir modelos/versões como cards clicáveis com modal dos itens vinculados.

Melhorias futuras sugeridas:

- Substituir campos numéricos de modelo/tipo nos formulários administrativos por `ChoiceField`/`ModelChoiceField` filtrado por banco, empresa e filial.
- Adicionar paginação/filtros por status e tipo na lista web e REST.
- Persistir assinatura em campos próprios ou tabela de auditoria, caso ela precise ter validade jurídica/histórica.
- Padronizar a URL REST para evitar dupla semântica `processos/processos/` em uma versão futura (`/api/{slug}/processos/instancias/`, por exemplo), mantendo compatibilidade atual.
