# [OPEN] Debug Session: nota-calc-duplicate

## Sintomas
- `POST /api/calcular/saveweb001/149/` retorna `400`.
- `PATCH /api/saveweb001/notasfiscais/notas-fiscais/notas/149/` retorna `500`.
- Stack aponta `Notas_Fiscais.models.Nota.MultipleObjectsReturned: get() returned more than one Nota -- it returned 2!`

## Contexto
- Ambiente Windows.
- Projeto em `d:\mobile-sps`.
- Tenant/licenca observada nos logs: `saveweb001`.
- Fluxo afetado: emissao web de nota fiscal.

## Hipoteses
1. O `get_object()` do `NotaViewSet` nao esta filtrando corretamente por empresa/filial/banco e encontra duas notas com o mesmo `id` logico no contexto atual.
2. O queryset do `NotaViewSet` usa `.using(banco)` mas mistura filtros insuficientes, e o roteamento multidb/multislug faz a busca bater em registros duplicados do tenant.
3. O endpoint `/api/calcular/<slug>/<id>/` recebe o `id` correto, mas a nota persistida ainda esta incompleta ou com dados inconsistentes, causando `400` antes do recarregamento da tela.
4. O fluxo de emissao cria uma nota e depois faz `PATCH` sobre outra representacao da mesma chave, por divergencia entre `slug`, alias de banco e estado em memoria.
5. Existe duplicidade real de registros na tabela de notas do tenant `saveweb001`, e a view so expoe o problema ao usar `get()`.

## Evidencias Coletadas
- Aguardando instrumentacao.

## Plano
1. Instrumentar `NotaViewSet` e endpoint de calculo para capturar alias, filtros, contagem e ids encontrados.
2. Reproduzir o fluxo com logs.
3. Confirmar ou rejeitar as hipoteses.
4. Aplicar a menor correcao possivel.
5. Validar com comparacao pre-fix e post-fix.
