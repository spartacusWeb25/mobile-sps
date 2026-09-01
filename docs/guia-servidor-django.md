# Servidor Django: setup, base local e novas bases

> Guia passo a passo — iniciar o servidor, configurar o ambiente, usar base local e cadastrar novas bases. Siga as etapas na ordem; cada uma diz ONDE digitar, O QUE o comando faz e COMO SABER QUE DEU CERTO. Baseado no código real do projeto (`core/settings.py`, `core/licencas_loader.py`, `setup_mobile.py`).

## Antes de começar: como o sistema organiza os bancos

O Mobile-SPS trabalha com **dois tipos de banco**, e entender isso evita 90% das confusões:

```text
                    ┌─────────────────────────────┐
  Login (CNPJ) ───> │  BASE DE CONTROLE (default) │   ← tabela licencas_web mora aqui
                    └──────────────┬──────────────┘
                                   │ o slug/CNPJ diz qual é a base da empresa
                    ┌──────────────▼──────────────┐
                    │  BASE DA EMPRESA (savexml…) │   ← dados de pedidos, produtos, etc.
                    └─────────────────────────────┘
```

1. **Base de controle** (conexão `default`): onde fica a tabela `licencas_web`, o cadastro de todas as empresas. A variável `USE_LOCAL_DB` no `.env` decide se essa base é a do **seu PC** (`LOCAL_DB_*`) ou a do **servidor remoto** (`REMOTE_DB_*`).
2. **Bases das empresas** (`savexml***`): cada linha da `licencas_web` guarda endereço, usuário e senha do banco daquela empresa. O sistema conecta nelas **dinamicamente** — quem manda é o que está cadastrado na linha.

Ou seja: `USE_LOCAL_DB=True` deixa a **base de controle** local, mas cada empresa continua apontando para onde a `licencas_web` mandar. Para uma empresa 100% local, a linha dela precisa apontar para o Postgres do seu PC (Parte E).

## Parte A — Instalação (faz uma vez só)

### Etapa 1 — Python 3.11+

1. Baixe em <https://www.python.org/downloads> e instale.
2. Na primeira tela do instalador, **marque "Add Python to PATH"**.

**Verificação:** num Prompt novo, `python --version` mostra `3.11` ou maior.

### Etapa 2 — PostgreSQL + pgAdmin

1. Baixe em <https://www.postgresql.org/download/windows> e instale (o pgAdmin vem junto).
2. A instalação pede uma **senha para o usuário `postgres`** — anote, vai usá-la no `.env`.
3. Deixe a porta padrão **5432**.

**Verificação:** o pgAdmin abre e conecta no servidor local com essa senha.

### Etapa 3 — Ambiente virtual (venv) e dependências

**Por quê:** o venv isola as bibliotecas do projeto.

```bat
cd C:\git\mobile-sps
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

> No Windows a ativação é `venv\Scripts\activate` (`source venv/bin/activate` é o equivalente Linux).
> No **PowerShell**, se der "execução de scripts desabilitada", rode uma vez:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Verificação:** o Prompt mostra `(venv)` no início da linha e o `pip install` termina sem erro (demora — são muitas dependências).

### Etapa 4 — Criar o arquivo `.env`

**Por quê:** o `.env` define a chave secreta do Django e onde está a base de controle.

Na **raiz do projeto** (`C:\git\mobile-sps`), crie o arquivo `.env` (com o ponto). Conteúdo mínimo para trabalhar local:

```env
SECRET_KEY=uma_chave_qualquer_bem_longa_aqui
DEBUG=True

USE_LOCAL_DB=True
LOCAL_DB_NAME=savexml1
LOCAL_DB_USER=postgres
LOCAL_DB_PASSWORD=senha_que_voce_criou_na_etapa_2
LOCAL_DB_HOST=localhost
LOCAL_DB_PORT=5432
```

- `LOCAL_DB_NAME` = nome da **base de controle** no seu Postgres (a que contém a `licencas_web` — ex.: a base do Savexml1 restaurada localmente).
- Os valores reais de produção (`REMOTE_DB_*`, e-mail etc.) ficam com o responsável do projeto — **nunca** suba o `.env` para o Git.

**Verificação:** o arquivo aparece na raiz, ao lado do `manage.py`.

## Parte B — Iniciar o servidor (o dia a dia)

### Etapa 5 — Ligar o servidor

```bat
cd C:\git\mobile-sps
venv\Scripts\activate
python manage.py runserver
```

**Verificação:** aparecem `BASE USADA: LOCAL` *(essa linha diz qual base de controle está ativa!)* e `Starting development server at http://127.0.0.1:8000/`.

Se aparecer `BASE USADA: REMOTA` quando você queria local → confira `USE_LOCAL_DB=True` no `.env`.

Parar: `Ctrl + C`. Mudou o `.env`? Pare e inicie de novo (só é lido na partida).

### Etapa 6 — Acessar no navegador

- Sistema: <http://127.0.0.1:8000>
- Login: documento `13446907000120`, usuário `mobile`, senha padrão do sistema.
- Admin: <http://127.0.0.1:8000/admin> (logar de novo).
- API (Swagger): <http://127.0.0.1:8000/api/schema/swagger-ui/>

### Etapa 7 — Servir também para o emulador/celular (app mobile)

O `runserver` normal só atende o navegador do próprio PC. Para o app enxergar o servidor:

```bat
python manage.py runserver 0.0.0.0:8000
```

E no app, o `src/api/config.ts` deve apontar para:

- **Emulador:** `http://10.0.2.2:8000/api` (endereço especial = "o PC onde o emulador roda")
- **Celular físico no Wi-Fi:** `http://IP-DO-PC:8000/api` (descubra o IP com `ipconfig`)

**Verificação:** o login do app funciona com os mesmos dados do navegador. (Guia do app: [guia-expo-android-apk.md](guia-expo-android-apk.md).)

## Parte C — Usar uma base local

### Etapa 8 — Colocar a base da empresa no seu Postgres

**Por quê:** para trabalhar sem tocar em produção, a base da empresa (`savexml***`) precisa existir no seu PC.

1. Consiga o **backup** da base com o responsável (`.backup` ou `.sql`).
2. No pgAdmin: **Databases → Create → Database...** → nomeie (ex.: `savexml123`) → Save.
3. Botão direito na base → **Restore...** → selecione o backup → Restore.

**Verificação:** expandindo a base no pgAdmin, aparecem as tabelas do sistema.

### Etapa 9 — Apontar a empresa para a base local

1. Com o servidor rodando: <http://127.0.0.1:8000/admin> → **Licencas_Web**.
2. Edite (ou crie — Parte D) a empresa: **db name** `savexml123` · **db host** `localhost` · **db port** `5432` · **db user** `postgres` · **db password** a senha do seu Postgres local.
3. Salve e **reinicie o servidor** (as conexões são carregadas na partida).

**Verificação:** logando com o CNPJ dessa empresa você vê os dados do backup — navegador **e** app operam sobre a base do seu PC.

## Parte D — Cadastrar uma base nova (nova empresa)

### Etapa 10 — Criar a linha na `licencas_web`

<http://127.0.0.1:8000/admin> → **Licencas_Web** → **Adicionar**:

| Campo | O que colocar |
| --- | --- |
| Slug | nome curto, sem espaços (ex.: `savenovo`) — **anote exatamente como digitou** |
| cnpj | CNPJ da empresa |
| db name | `savexml***` (banco da empresa) |
| db host | `localhost` (base local) ou IP do servidor (ex.: `64.181.163.190`) |
| db port | `5432` |
| db user | `postgres` |
| db password | senha do Postgres daquele host |
| plano | qualquer um dos três |

### Etapa 11 — Rodar o setup inicial do tenant

**Por quê:** o `setup_mobile.py` cria as parametrizações iniciais e o usuário admin padrão.

```bat
python setup_mobile.py --tenant "savenovo"
```

O nome do `--tenant` tem que ser **exatamente igual ao Slug** da Etapa 10.
Dica: `python setup_mobile.py --all` roda o setup para **todas** as bases da `licencas_web`.

**Verificação:** o script termina sem erro e o login na nova empresa funciona com o admin padrão.

## Criar um novo app Django

```bat
python manage.py startapp nomedoapp
```

Depois reorganize para o padrão de **arquitetura horizontal** do projeto (camadas `rest/`, `services/`, `web/`) — ver [visão geral da arquitetura](arquitetura/visao-geral.md).

## Resumo de comandos

```bat
:: ligar o servidor (todo dia)
cd C:\git\mobile-sps
venv\Scripts\activate
python manage.py runserver              & :: só navegador
python manage.py runserver 0.0.0.0:8000 & :: navegador + emulador/celular

:: endereços
:: http://127.0.0.1:8000                     → sistema
:: http://127.0.0.1:8000/admin               → admin (Licencas_Web)
:: http://127.0.0.1:8000/api/schema/swagger-ui/ → API

:: nova base
:: admin → Licencas_Web → Adicionar → salvar
python setup_mobile.py --tenant "slug"
```

## Solução de problemas — erros comuns

1. **`(venv)` não aparece / "execução de scripts desabilitada"** → no PowerShell: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`; ou use o cmd comum.
2. **`connection refused` / `could not connect to server`** → PostgreSQL parado (Serviços do Windows → postgresql → Iniciar) ou host/porta errados no `.env`.
3. **`password authentication failed`** → senha do `.env` ou da linha na `licencas_web` diferente da senha real do Postgres.
4. **Servidor liga, mas `BASE USADA: REMOTA`** → `USE_LOCAL_DB=True` ausente ou errado no `.env`; reinicie após corrigir.
5. **Mudei a `licencas_web` e não fez efeito** → reinicie o servidor — as conexões são carregadas na partida.
6. **`Porta 8000 already in use`** → outro servidor aberto; feche-o ou use `runserver 0.0.0.0:8001` (e ajuste a URL no app).
7. **App no emulador não conecta, navegador funciona** → servidor sem `0.0.0.0:8000`, ou `config.ts` apontando para `localhost` em vez de `10.0.2.2`.

---

*Padronizado em 2026-09-01. Fonte: documento "GUIA_SERVIDOR_DJANGO.md" (substitui a versão resumida anterior deste arquivo, que vinha do README da raiz).*
