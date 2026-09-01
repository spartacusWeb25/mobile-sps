# Documentação de Infraestrutura — Mobile-SPS

Sistema web (Django) do Spartacus SPS. Documento de referência de servidor, domínio, acessos e operação.

> Campos marcados com **\[PREENCHER\]** aguardam informação. Manter este documento atualizado a cada mudança de infraestrutura. **Nunca gravar senhas ou chaves neste documento** — registrar apenas ONDE elas estão guardadas e QUEM tem acesso.

---

## 1\. Visão geral

| Item | Valor |
| :---- | :---- |
| Sistema | Mobile-SPS (versão web/Django do Spartacus SPS) |
| URL de produção | [https://mobile-sps.site](https://mobile-sps.site) (login em `/web/login/`) |
| API / Swagger | [https://mobile-sps.site/api/schema/swagger-ui/](https://mobile-sps.site/api/schema/swagger-ui/) |
| Repositório (espelho) | [https://github.com/spartacusWeb25/mobile-sps](https://github.com/spartacusWeb25/mobile-sps) |
| Repositório de origem (onde roda o CI) | **\[PREENCHER\]** |
| Stack | Python 3.11 · Django · Gunicorn \+ Daphne · Nginx · PostgreSQL · Redis (produção) |
| Multi-tenant | Sim — uma base `savexml***` por empresa, roteada por slug/licença web |

## 2\. Domínio e DNS

| Item | Valor |
| :---- | :---- |
| Domínio | `mobile-sps.site` |
| Registrador | Namecheap (namecheap.com) |
| Registrado em | 27/08/2025 |
| Vencimento | 27/08 de cada ano — **conferir auto-renew ativo** |
| Titular da conta Namecheap | **\[PREENCHER — nome e e-mail de login\]** |
| Onde a credencial está guardada | **\[PREENCHER\]** |
| Nameservers | Namecheap BasicDNS (`dns101/dns102.registrar-servers.com`) — confirmar após a renovação de 2026 |
| Registro A `@` | `168.75.73.117` |
| Registro A `www` | **\[PREENCHER — confirmar se usado\]** |
| TTL | 60 segundos |

## 

## 3\. Servidor de aplicação

| Item | Valor |
| :---- | :---- |
| Provedor | Oracle Cloud |
| Conta Oracle Cloud (titular/e-mail) | **\[PREENCHER\]** |
| Tipo de instância / região | **\[PREENCHER — verificar no console; se Always Free, risco de recuperação por ociosidade\]** |
| IP público | `168.75.73.117` |
| SO / usuário | Linux (Ubuntu) / `ubuntu` |
| Acesso SSH | `ssh -i SPARTACUS.pem ubuntu@168.75.73.117` |
| Chave `SPARTACUS.pem` — quem guarda | **\[PREENCHER\]** |
| Cópia de segurança da chave | **\[PREENCHER — onde\]** |

### Layout no servidor

/home/ubuntu/mobile-sps/

├── blue/       \# ambiente A do deploy blue/green

├── green/      \# ambiente B

├── current \-\> blue|green   \# symlink para o ambiente ativo

├── repo/       \# clone do repositório usado pelo deploy

├── venv/       \# virtualenv Python 3.11 compartilhado

└── .env        \# variáveis de produção (copiado para o ambiente alvo a cada deploy)

### Serviços (systemd)

| Serviço | Função | Notas |
| :---- | :---- | :---- |
| `gunicorn` | Aplicação Django (WSGI) | bind `127.0.0.1:8000`, 9 workers, 2 threads, timeout 120s, `Restart=always` |
| `daphne` | Websockets/ASGI | reiniciado junto no deploy |
| `nginx` | Proxy reverso | config em `/etc/nginx/sites-available/default` |
| `docker` (`pg_backup`) | Backup do PostgreSQL | ver seção 4 |

Health check interno da aplicação: `http://127.0.0.1:8000/health/`

### Variáveis de produção (`/home/ubuntu/mobile-sps/.env`)

Principais chaves esperadas (valores **não** documentados aqui): `SECRET_KEY`, `DEBUG=False`, `USE_LOCAL_DB=False`, `REMOTE_DB_*`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (deve incluir `https://mobile-sps.site`), `EMAIL_*`, `USE_REDIS_CACHE`/`CELERY_BROKER_URL`. Backup do `.env` de produção: **\[PREENCHER — onde está guardada a cópia\]**

## 4\. Banco de dados

| Item | Valor |
| :---- | :---- |
| SGBD | PostgreSQL |
| Host | `base.rtalmeida.com.br` \= `64.181.163.190`, porta 5432 |
| Bases | Uma `savexml***` por empresa/tenant \+ bases de controle |
| Usuário da aplicação | `savexml***` por base (senhas disponíveis no licencas) |
| Superusuário `postgres` | Senha padrão da empresa |

### Backup

Container Docker `pg_backup` (no servidor de treinamento — confirmar se também roda no de produção: **\[PREENCHER\]**):

- Backup diário (\~11:29) de todas as bases, dumps comprimidos em `/home/ubuntu/pg_backups/`  
- Retenção automática de 7 dias  
- Recria diariamente a `base_modelo` a partir da estrutura da `saveweb001` (base modelo mais recente)  
- Backup externo/off-site: **\[PREENCHER — existe? onde?\]**

## 5\. CI/CD — deploy automático

Fluxo (definido em `.github/workflows/deploy.yml` no repositório de origem):

1. Push na branch `main`  
2. Espelha o código para `spartacusWeb25/mobile-sps` (removendo os workflows) via GitHub App  
3. Deploy via SSH (appleboy/ssh-action) no servidor Oracle  
4. Rsync do código para o ambiente inativo (blue ou green), instala dependências se `requirements.txt` mudou  
5. Troca o symlink `current`, reinicia `gunicorn` \+ `daphne`  
6. Health check em `/health/` — se falhar, o deploy aborta  
7. E-mail de sucesso/falha ("Deploy SPS — Sucesso/Falha") via Gmail

| Item | Valor |
| :---- | :---- |
| GitHub environment | `Mobile-Sps` |
| Secrets usados | `ORACLE_HOST`, `ORACLE_USER`, chave SSH, `GH_APP_ID` \+ chave privada do App, `SMTP_USER`/senha |
| Admin da organização/repos GitHub | **\[PREENCHER\]** |
| Conta Gmail que recebe e-mails de deploy | **\[PREENCHER\]** |

Todo merge na `main` vai para produção automaticamente. Reiniciar serviços manualmente só quando necessário — o deploy já faz isso.

## 6\. Acessos e credenciais — mapa

| Acesso | Titular / quem tem | Onde a credencial está guardada |
| :---- | :---- | :---- |
| Conta Namecheap (domínio) | **\[PREENCHER\]** | **\[PREENCHER\]** |
| Console Oracle Cloud | **\[PREENCHER\]** | **\[PREENCHER\]** |
| Chave SSH `SPARTACUS.pem` | **\[PREENCHER\]** | **\[PREENCHER\]** |
| PostgreSQL (`postgres` e `savexml***`) | **\[PREENCHER\]** | **\[PREENCHER\]** |
| GitHub org `spartacusWeb25` (admin) | **\[PREENCHER\]** | **\[PREENCHER\]** |
| Gmail do CI (`SMTP_USER`) | **\[PREENCHER\]** | **\[PREENCHER\]** |
| Admin Django (`/admin`) | usuário `mobile` (ver README do repo) | **\[PREENCHER\]** |
| Mercado Livre (app/integração) | **\[PREENCHER\]** | **\[PREENCHER\]** |
| APIs de boletos (Sicredi/Itaú — certificados) | **\[PREENCHER\]** | **\[PREENCHER\]** |

Recomendação: centralizar tudo em um cofre de senhas da empresa (ex.: Bitwarden/1Password) em vez de contas pessoais.

## 7\. Integrações externas

- **Mercado Livre** — OAuth com redirect para `https://mobile-sps.site/` (`mercado_livre.py`); quebra se o domínio mudar  
- **Etiquetas/QR code** — URLs `https://mobile-sps.site/p/<hash>` impressas em etiquetas físicas; dependem do domínio estável  
- **Boletos** — serviços Sicredi e Itaú no app `boletos/` (certificados SSL: ver `boletos/readmeitau.md`)  
- **E-mail transacional** — SMTP configurado no `.env` de produção: **\[PREENCHER — provedor/conta\]**  
- **SEFAZ / fiscal** — gateway em `transportes/services/sefaz_gateway.py` e apps fiscais

## 8\. Operação e manutenção

### Atualização manual (sem CI)

cd /home/ubuntu/mobile-sps

source venv/bin/activate

git pull

python manage.py collectstatic \--noinput

sudo systemctl restart gunicorn daphne

### Logs

sudo journalctl \-u gunicorn \-n 100        \# aplicação

sudo tail \-f /var/log/nginx/error.log     \# nginx erros

sudo tail \-f /var/log/nginx/access.log    \# nginx acessos

### Runbook — sistema fora do ar

1. Testar `http://168.75.73.117` — se abrir, o problema é domínio/DNS (Namecheap); se não, continuar  
2. Verificar deploy recente com falha (Actions / e-mail "Deploy SPS — Falha")  
3. SSH no servidor → `sudo systemctl status gunicorn daphne nginx`  
4. `df -h` (disco cheio) e logs acima  
5. `sudo systemctl restart gunicorn daphne && sudo nginx -t && sudo systemctl restart nginx`  
6. SSH não conecta → console Oracle Cloud (instância parada/recuperada?)

### Nova base/empresa (resumo — detalhes no README do repo)

1. Cadastrar a licença em Licenças Web no `/admin` (slug, CNPJ, db name `savexml***`, host do banco, plano)  
2. `python setup_mobile.py --tenant "<slug>"` (slug idêntico ao do admin)

## 9\. Ambiente de desenvolvimento local (resumo)

- Python 3.11 \+ venv, dependências em `requirements.txt`  
- `.env` local com `USE_LOCAL_DB=True` e credenciais do PostgreSQL local  
- Base local exige licença cadastrada em Licenças Web no `/admin` \+ `setup_mobile.py --tenant`  
- Guia completo: `README.md` do repositório

---

## Pendências de preenchimento

- [ ] Titulares e local de guarda de cada credencial (seção 6\)  
- [ ] Repositório de origem do CI  
- [ ] Detalhes da instância Oracle (tipo, região, conta)  
- [ ] Confirmar backup do banco em produção e existência de cópia off-site  
- [ ] Backup do `.env` de produção e da chave `SPARTACUS.pem`  
- [ ] Registro A do `www` e configuração final do DNS pós-renovação


---

*Movido para docs/ e mantido no padrão da documentação em 2026-09-01. Fonte original: `docs/documentacao-infraestrutura.md`.*
