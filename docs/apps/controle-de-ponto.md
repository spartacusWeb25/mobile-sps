# Controle de Ponto

> Registro de ponto de colaboradores em arquitetura horizontal inspirada em DDD (domínio, portas, casos de uso, infra).

| Localização | Base da API | Camadas |
| --- | --- | --- |
| `controledePonto/` | rotas em `Rest/urls.py` | models · Rest (dominio · aplicacoes · views) · repositorios |

## Visão geral

O app foi desenhado para manter as regras de negócio independentes do framework, com fronteiras explícitas:

| Camada | Pasta | Conteúdo |
| --- | --- | --- |
| Domínio — entidades | `Rest/dominio/entidades/` | `RegistroPonto` puro (sem Django; `id` opcional) |
| Domínio — portas | `Rest/dominio/portas/` | Interface `RepositorioPonto` |
| Aplicação | `Rest/aplicacoes/casos_uso/` | `CasosDeUsoPonto`: registra, lista e consulta |
| Infraestrutura | `repositorios.py` | `RepositorioPontoModelo` (ORM, `objects.using(banco)`) |
| Apresentação | `Rest/views.py`, `serializers.py`, `urls.py`, `permissoes.py` | ViewSet, serializer DRF, rotas e permissões |

**Regra de dependência**: views/serializers conhecem Django/DRF, mas não regras de negócio; casos de uso dependem apenas de portas; entidades de domínio não dependem de Django.

## Fluxo

1. HTTP → `RegistroPontoViewSet` resolve o `banco` (query param ou `core.registry.get_licenca_db_config`).
2. `create`: serializer valida → caso de uso cria `RegistroPonto` e chama a porta `registrar`.
3. `list`: filtra por `colaborador_id`/banco e serializa.
4. Infra grava/consulta via `models.RegistroPonto.objects.using(banco)`, convertendo entidade ↔ modelo.

## Regras de negócio

- `data_hora` é somente leitura no serializer — o caso de uso define o momento da marcação.
- `listar_por_id` retorna lista (múltiplos registros por colaborador).

## Pontos de extensão

- Validações de domínio (ex.: alternância entrada/saída) nos casos de uso.
- Políticas de acesso em `Rest/permissoes.py`.
- Testes unitários por camada (pendentes).

---

*Padronizado em 2026-09-01. Fonte: `controledePonto/ARQUITETURA.md` (movido para docs).*
