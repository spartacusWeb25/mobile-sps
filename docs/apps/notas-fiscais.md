# Notas Fiscais (NF-e / NFC-e)

> Emissão de NF-e (modelo 55) e NFC-e (modelo 65): domínio, cálculo fiscal, XML PyNFe, assinatura A1 e transmissão à SEFAZ.

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `Notas_Fiscais/` | `/api/{slug}/notasfiscais/` | models · services · dominio · aplicacao · infrastructure · REST · api · Web |

## Visão geral

Módulo estruturado em camadas: **Domínio** (models), **Serviços** (regras de negócio), **Aplicação** (DTO + PyNFe), **Infraestrutura** (certificado e SEFAZ), **APIs REST** e **Web** (`templates_spsWeb/notas/`). O fluxo de emissão completo, com diagrama, está em [Emissão de NF-e](../arquitetura/emissao-nfe.md); o cálculo de impostos está em [Motor Fiscal](../arquitetura/motor-fiscal.md).

## Modelos principais

| Modelo | Tabela | Relação | Descrição |
| --- | --- | --- | --- |
| `Nota` | `nf_nota` | N–1 `Filiais` (emitente), N–1 `Entidades` (destinatário) | Cabeçalho; chave lógica única `empresa+filial+modelo+serie+numero` |
| `NotaItem` | `nf_nota_item` | N–1 `Nota`, N–1 `Produtos` | Itens (índices em nota e produto) |
| `NotaItemImposto` | `nf_item_imposto` | 1–1 `NotaItem` | Impostos por item (ICMS/IPI/PIS/COFINS/FCP + CBS/IBS) |
| `Transporte` | `nf_transporte` | 1–1 `Nota` | Frete/veículo |
| `NotaEvento` | `nf_nota_evento` | N–1 `Nota` | Eventos: autorização, cancelamento, CC-e etc. |
| `NotaFiscal` / `Infvv` (legado) | `nfevv` / `infvv` | managed=False | Somente leitura/ETL |

## Serviços

- `NotaService`: criar/atualizar/gravar (rascunho)/transmitir/cancelar/inutilizar; normaliza dados e valida participantes.
- `CalculoImpostosService`: resolve CFOP/NCM/alíquotas via `CFOP.services.MotorFiscal` e grava `nf_item_imposto`. Transacional por nota.
- `TransporteService`: `update_or_create` dos dados de frete.
- `EventoService`: registra eventos e atualiza status.
- `EmissaoService`: calcula impostos → monta DTO (`dominio/builder.py`) → constrói XML (`aplicacao/construir_nfe_pynfe.py`) → assina e transmite (`infrastructure/sefaz_adapter.py`).

## API

| Método | Rota | Descrição |
| --- | --- | --- |
| CRUD | `notas-fiscais/notas/` | Notas (detalhe inclui `itens`, `impostos`, `transporte`) |
| `POST` | `notas-fiscais/notas/{id}/transmitir/` | Transmite (status → `100`) |
| `POST` | `notas-fiscais/notas/{id}/cancelar/` | Cancela (status → `101`, gera evento) |
| `GET` | `notas-fiscais/emitir/{slug}/{nota_id}/` | Emissão direta de nota existente |
| — | `notas-eventos/`, autocompletes de entidades/produtos | Apoio |

Filtros de listagem: `empresa`, `filial`.

Payload mínimo de criação de NF-e 55:

```json
{
  "modelo": "55", "serie": "001", "numero": 123,
  "tipo_operacao": 1, "finalidade": 1, "ambiente": 2,
  "destinatario": "<enti_clie>",
  "itens": [{
    "produto": "<prod_codi>", "quantidade": "1", "unitario": "100.00",
    "desconto": "0", "cfop": "5102", "ncm": "<ncm>",
    "cst_icms": "000", "cst_pis": "01", "cst_cofins": "01"
  }]
}
```

## Parâmetros da nota

- `modelo`: `55` NF-e · `65` NFC-e
- `ambiente`: `1` produção · `2` homologação
- `tipo_operacao`: `0` entrada · `1` saída
- `finalidade`: `1` normal · `2` complementar · `3` ajuste · `4` devolução
- Transporte: `modalidade_frete`, `transportadora`, `placa_veiculo`, `uf_veiculo`
- Status SEFAZ relevantes: `100` autorizada · `101` cancelada

## Configuração

- **Certificado A1**: arquivo em `Filiais.empr_cert_digi`, senha em `Filiais.empr_senh_cert`; `Filiais.empr_ambi_nfe` orienta o ambiente default.
- **Rotas**: incluídas por `core/api_router.py` sob `/api/{slug}/notasfiscais/`.
- **Multi-tenant**: banco resolvido pelo slug (ver [visão geral](../arquitetura/visao-geral.md)).

## Execução e testes

- Emissão de teste: `python manage.py emitir_notas_teste --empresa <E> --filial <F>` (modelos 55 e 65).
- Web: `/web/{slug}/notas-fiscais/` para listar/emitir/cancelar/inutilizar.
- Testes: `python manage.py test Notas_Fiscais`. Plano de testes: verificar listagem/detalhe/criação/cancelamento/transmissão, uso de `select_related/prefetch_related` no `NotaViewSet`, e unicidade da chave lógica.

## Pontos de atenção

- **IBS/CBS (Reforma Tributária)**: a PyNFe ainda não suporta os campos nativamente; eles são carregados numa lista `_itens_extra` e injetados manualmente no XML pelo `sefaz_adapter` **apenas quando > 0** (evita erro 225).
- Pendência registrada: campos `id_csrt`/`hash_csrt` no `ResponsavelTecnicoDTO` (obter dos dados da filial ou dos XMLs do Spartacus).
- Erros comuns: certificado inválido (conferir campos da filial), CFOP/NCM inexistentes (validar cadastros e `MapaCFOP`), falha de conexão SEFAZ (rede/ambiente/PyNFe).

---

*Padronizado em 2026-09-01. Fontes: `Notas_Fiscais/docs/*` (readme, Arquitetura, Manual, Testes).*
