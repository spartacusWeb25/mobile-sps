# Entidades

> Cadastro unificado de clientes, fornecedores, vendedores, funcionários e demais pessoas físicas/jurídicas do sistema.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Entidades/` | `/api/{slug}/entidades/` e `/api/{slug}/entidades-login/` | models · rest |

## Visão geral

Todo participante de uma operação (venda, compra, OS, título) é uma **Entidade**. O tipo é definido em `enti_tipo_enti`: `CL` cliente, `FO` fornecedor, `AM` ambos, `VE` vendedor, `FU` funcionário, `OU` outros. O módulo também expõe o **login do cliente** (`entidades-login`), que permite ao cliente cadastrado autenticar-se e acessar seus próprios pedidos, orçamentos e ordens de serviço.

## Modelos principais

| Modelo | Tabela | Chave | Descrição |
| --- | --- | --- | --- |
| `Entidades` | `entidades` (managed=False) | `enti_clie` (PK, BigInteger) | Cadastro da entidade |

Campos relevantes: `enti_empr` (empresa, obrigatório), `enti_nome`/`enti_fant`, documentos (`enti_cpf`, `enti_cnpj`, `enti_insc_esta`), endereço completo (`enti_cep`, `enti_ende`, `enti_nume`, `enti_cida`, `enti_esta`) e contatos (`enti_fone`, `enti_celu`, `enti_emai`).

## API

### Cadastro (`/api/{slug}/entidades/`)

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `entidades/` | Cadastro completo de entidades |

Filtros: `enti_empr`, `enti_tipo_enti`, `enti_nome` (contém), `enti_cida`, `enti_esta`, `search` (nome e fantasia).

### Portal do cliente (`/api/{slug}/entidades-login/`)

| Método | Rota | Descrição |
| --- | --- | --- |
| `POST` | `login/` | Autenticação do cliente |
| `GET` | `dashboards/cliente-dashboard/` | Dashboard do cliente logado |
| CRUD | `entidades/` | Cadastro do próprio cliente |
| `GET` | `entidades/buscar-endereco/` | Busca de endereço (CEP) |
| CRUD | `pedidos/`, `pedidos-geral/`, `orcamentos/`, `ordem-servico/`, `os/` | Acesso do cliente aos próprios documentos |

## Regras de negócio

- `enti_clie` é o código único da entidade e chave de referência usada pelos demais apps (`pedi_forn`, `titu_clie`, `orde_enti` etc.).
- CPF/CNPJ são opcionais no modelo; validar conforme o tipo de entidade na camada de serviço.
- Vendedores também são entidades (tipo `VE`) — pedidos referenciam vendedor por código de entidade.

## Integrações

- **Pedidos / Orçamentos**: cliente (`pedi_forn`) e vendedor (`pedi_vend`).
- **Contas a Receber / Pagar**: cliente (`titu_clie`) e fornecedor (`titu_forn`).
- **Ordem de Serviço, Lista de Casamento, Notas Fiscais**: destinatários e participantes.

## Pontos de atenção

- Tabela não gerenciada pelo Django (`managed=False`) — alterações de esquema são feitas direto no banco.
- Não há constraint de unicidade em CPF/CNPJ; duplicatas devem ser tratadas na aplicação.

---

*Padronizado em 2026-09-01. Fonte: `Entidades/README.md`.*
