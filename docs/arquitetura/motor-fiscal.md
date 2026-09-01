# Motor Fiscal

> Arquitetura do cálculo de impostos: horizontal e determinística, para facilitar auditoria, correções e testes.

## Componentes

| Componente | Arquivo | Responsabilidade |
| --- | --- | --- |
| `MotorFiscal` | `CFOP/services/services.py` | Orquestrador: coordena busca de dados (NCM, CFOP, alíquotas) e executa as calculadoras. Interface: `calcular_item(ctx, item, tipo_oper, base_manual)` |
| `FiscalContext` | — | Dataclass **imutável** com todo o estado do cálculo de um item (produto, NCM, CFOP, regras, alíquotas, ICMS origem/destino). Elimina side effects e dependências globais |
| Calculadoras (`TaxCalculator`) | `CFOP/services/services.py` | Uma por tributo: `IPICalculator`, `ICMSCalculator` (próprio + ST), `PISCOFINSCalculator`, `IBSCBSCalculator` (Reforma Tributária) |
| `CalculoImpostosService` | `Notas_Fiscais/services/calculo_impostos_service.py` | Ponte entre o motor e os modelos de nota; persiste em `NotaItem`/`NotaItemImposto`; transacional por nota |
| `ResolverAliquotaPorRegime` | `CFOP/services/auxiliares.py` | Modula alíquotas base conforme regime da empresa (Simples vs Normal); prepara IBS/CBS |
| `ResolverCST` | `CFOP/services/services.py` | Determina CST/CSOSN: prioriza Overrides > Regime > Defaults (ICMS, IPI, PIS/COFINS) |
| `ResolverIncidencia` | `Notas_Fiscais/services/calculo_impostos_service.py` | Nível de negócio (nota): ajusta regras fiscais antes do cálculo — ex.: isenções (Suframa) alterando flags do CFOP **em memória** |

## Fluxo de dados

1. **Emissão**: `EmissaoNotaService` chama `CalculoImpostosService.aplicar_impostos(nota)`.
2. **Preparação**: `ResolverIncidencia` aplica regras de negócio ao CFOP; o serviço monta o `FiscalContext` (empresa, cliente, produto).
3. **Cálculo** (`MotorFiscal`, sequencial e explícito):
   resolução de CFOP (operação + estados) → `ResolverAliquotaPorRegime` → overrides de CFOP/NCM → `ResolverCST` → calculadoras em sequência.
4. **Resultado**: dicionário "pacote" com bases, alíquotas, valores e CSTs.
5. **Persistência**: gravação em `nf_item_imposto`.

## Matriz de decisão de regime

| Imposto | Regime Normal (3) | Simples Nacional (1/2) |
| --- | --- | --- |
| ICMS | CST 00, 10, 20… | CSOSN 101, 102… |
| IPI | CST 50, 51… | Geralmente N/A ou 49/99 |
| PIS/COFINS | CST 01, 02… | CST 49 ou 99 |
| IBS/CBS | Full (2026+) | Transição/diferenciado |

## Testes

`CFOP/tests/test_services.py` e `CFOP/tests/test_resolvers.py` cobrem cálculo dos tributos, decisão de CST/CSOSN, alíquotas por regime e integração do motor.

---

*Padronizado em 2026-09-01. Fonte: `Notas_Fiscais/DOC_ARQUITETURA_FISCAL.md` (movido para docs).*
