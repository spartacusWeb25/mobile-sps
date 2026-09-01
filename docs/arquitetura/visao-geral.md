# Arquitetura Geral do Mobile-SPS

> Como o sistema é organizado: multi-tenant por slug, arquitetura horizontal por app e roteamento de banco.

## Stack

Python 3.11 · Django + Django REST Framework · Gunicorn (WSGI) + Daphne (ASGI/websockets) · Nginx · PostgreSQL · Redis/Celery (produção) · PyNFe (fiscal).

## Multi-tenant por slug

Cada cliente tem **seu próprio banco PostgreSQL** (`savexml***`). O banco `default` guarda os metadados globais (`LicencaWeb`, `Plano`). O slug na URL identifica o tenant e o `LicencaDBRouter` roteia a query para o banco correto:

```text
/api/{slug}/app/recurso/     ← API REST
/web/{slug}/...              ← versão web
        ↑
   identifica o banco do cliente
```

Pontos-chave:

- `core/licenca_context.py` e `core/utils.get_db_from_slug` resolvem slug → configuração de banco. A fonte é a tabela `licencas_web_licencaweb` (banco `default`), com fallback para `core/licencas.json` e credenciais do `.env` (ver [migração de licenças web](licencas-web-migracao.md)).
- `core/db_router.py` + `core/middleware.py` aplicam o roteamento por request.
- Services devem receber e repassar `db_alias`, `empresa` e `filial` explicitamente (padrão do app `processos`) para evitar vazamento entre tenants.
- **Cuidado**: consultas a modelos do banco `default` (ex.: `Plano`, `LicencaWeb`) dentro de um request de tenant devem usar `.using('default')` explicitamente.

Praticamente todas as tabelas de negócio são segregadas também por **empresa** (`*_empr`) e **filial** (`*_fili`) dentro do banco do tenant.

## Arquitetura horizontal por app

Cada app Django segue camadas com responsabilidade única (o app `Pedidos` é a referência):

```text
app/
├── models.py         # Tabelas e relações (ORM)
├── rest/             # Camada de API (DRF)
│   ├── serializers.py    # Contratos DTO
│   ├── urls.py           # Endpoints
│   └── views/            # Controle da API (views magras)
├── services/         # CORE: regras de negócio e integrações
└── web/              # Interface web (Django Templates)
    ├── forms.py
    ├── urls.py
    └── views/
```

Regras:

- **Views magras** — lógica de negócio vive em `services/`.
- API nova → padrão `rest/`; tela web → padrão `web/`.
- Campos de banco seguem o padrão **prefixo de 4 letras** por tabela (`pedi_*`, `iped_*`, `tdvl_*`, `titu_*`, …).
- Apps mais recentes (`controledePonto`, `OrdemdeServico`) aprofundam o padrão com domínio/portas/casos de uso (DDD): domínio decide o que pode, service executa o fluxo, repository fala com o banco, view entrega HTTP, handler traduz erro.
- Novo app: `python manage.py startapp nome` e reorganizar para o padrão acima.

## Convenções

- Muitas tabelas de negócio são `managed=False` (legado compartilhado com o Spartacus SPS) — alterações de esquema são feitas no banco, não por migração Django.
- Views SQL auxiliares (`pedidos_geral`, `produtos_detalhados`) precisam ser criadas em cada tenant.
- Swagger disponível em `/api/schema/swagger-ui/`.

## Documentos relacionados

- [Motor Fiscal](motor-fiscal.md) — cálculo de impostos.
- [Emissão de NF-e](emissao-nfe.md) — fluxo completo de emissão.
- [Setup do ambiente](../guia-servidor-django.md) e [Infraestrutura](../infraestrutura.md).

---

*Padronizado em 2026-09-01. Fontes: `README.md` (raiz), `Licencas/README.md`, `docs/processos_rest_react_native.md`.*
