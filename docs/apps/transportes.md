# Transportes (CT-e e MDF-e)

> Emissão e gestão de CT-e e MDF-e, com API REST consumida pelo app React Native.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `transportes/` | `/api/{slug}/transportes/api/` | models · rest · services (inclui `sefaz_gateway`) |

## Visão geral

Cobre o ciclo dos documentos fiscais de transporte: criação de rascunho, preenchimento, cálculo de impostos, emissão (XML assinado + chave), vínculo de documentos ao MDF-e e encerramento. Autenticação exigida (`IsAuthenticated`); multi-banco resolvido pelo slug.

## API

### CT-e

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET`/`POST` | `ctes/` | Listar / criar rascunho |
| `PATCH` | `ctes/{id}/` | Atualizar |
| `POST` | `ctes/{id}/emitir/` | Emite; retorna `{status, mensagem, protocolo, recibo}` (`autorizado`, `recebido`, `processando`, `rejeitado`) |
| `GET` | `ctes/{id}/calcular-impostos/?cfop={cfop_id}` | Cálculo de impostos |

### MDF-e

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET`/`POST`/`PATCH` | `mdfes/`, `mdfes/{id}/` | CRUD básico |
| `POST` | `mdfes/{id}/emitir/` (ou `gerar-xml/`) | Emite: XML assinado + chave |
| `POST` | `mdfes/{id}/encerrar/` | Encerramento manual (payload opcional `{uf, cmun}`) |
| `POST` | `mdfes/{id}/encerrar-automatico/` | Encerramento automático |
| `GET`/`POST` | `mdfes/{id}/documentos/` | Documentos vinculados (`{tipo_doc, chave, cmun_descarga, xmun_descarga}`) |

## Fluxo sugerido (mobile)

1. Criar CT-e/MDF-e → 2. completar por `PATCH` → 3. (MDF-e) vincular documentos → 4. emitir → 5. (MDF-e) encerrar após a viagem.

Códigos de retorno: `200` OK · `400` payload inválido · `401/403` autenticação/permissão · `500` erro interno (campo `error`).

## Integrações

- **SEFAZ**: `transportes/services/sefaz_gateway.py`.
- **CFOP**: cálculo de impostos do CT-e.

---

*Padronizado em 2026-09-01. Fonte: `transportes/README_REACT_NATIVE.md`.*
