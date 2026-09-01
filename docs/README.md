# Documentação do Mobile-SPS

Documentação técnica do sistema Mobile-SPS (versão web/Django do Spartacus SPS), voltada a desenvolvedores. Cada documento segue o [template padrão](TEMPLATE.md) — enxuto, com tabelas de modelos e endpoints, pensado para entender cada parte em poucos minutos.

Ao alterar um módulo, atualize o documento correspondente e a data no rodapé. Para documentar novos módulos, copie o `TEMPLATE.md`.

## Guias de desenvolvimento

| Documento | Conteúdo |
| --- | --- |
| [guia-servidor-django.md](guia-servidor-django.md) | Passo a passo completo: instalar, configurar o `.env`, rodar o servidor local, servir para o app mobile, usar base local e cadastrar novas bases (tenants) |
| [guia-expo-android-apk.md](guia-expo-android-apk.md) | Rodar o app React Native com Expo (emulador ou celular) e gerar o APK |
| [infraestrutura.md](infraestrutura.md) | Servidor de produção, domínio/DNS, serviços (systemd), CI/CD blue/green, runbook de queda e mapa de acessos |
| [containers-backup.md](containers-backup.md) | Container `pg_backup`: backup diário, retenção e regeneração da `base_modelo` |

## Arquitetura

| Documento | Conteúdo |
| --- | --- |
| [visao-geral.md](arquitetura/visao-geral.md) | Stack, multi-tenant por slug, roteamento de banco e arquitetura horizontal por app |
| [motor-fiscal.md](arquitetura/motor-fiscal.md) | Cálculo de impostos: MotorFiscal, FiscalContext, calculadoras e resolvers |
| [emissao-nfe.md](arquitetura/emissao-nfe.md) | Fluxo completo de emissão: modelos, cálculo, DTO, PyNFe, assinatura e SEFAZ |
| [licencas-web-migracao.md](arquitetura/licencas-web-migracao.md) | Migração do roteamento de licenças: `core/licencas.json` para a tabela `licencas_web_licencaweb` |

## Módulos (apps)

### Comercial

| App | Documento |
| --- | --- |
| Pedidos | [apps/pedidos.md](apps/pedidos.md) |
| Orçamentos | [apps/orcamentos.md](apps/orcamentos.md) |
| Caixa Diário (PDV) | [apps/caixa-diario.md](apps/caixa-diario.md) |
| Trocas e Devoluções | [apps/trocas-devolucoes.md](apps/trocas-devolucoes.md) |
| Pisos (vertical) | [apps/pisos.md](apps/pisos.md) |
| Lista de Casamento | [apps/lista-casamento.md](apps/lista-casamento.md) |

### Cadastros e estoque

| App | Documento |
| --- | --- |
| Entidades | [apps/entidades.md](apps/entidades.md) |
| Produtos | [apps/produtos.md](apps/produtos.md) |
| Entradas de Estoque | [apps/entradas-estoque.md](apps/entradas-estoque.md) |
| Saídas de Estoque | [apps/saidas-estoque.md](apps/saidas-estoque.md) |
| Agrícola | [apps/agricola.md](apps/agricola.md) |

### Financeiro

| App | Documento |
| --- | --- |
| Contas a Pagar | [apps/contas-a-pagar.md](apps/contas-a-pagar.md) |
| Contas a Receber | [apps/contas-a-receber.md](apps/contas-a-receber.md) |

### Fiscal

| App | Documento |
| --- | --- |
| Notas Fiscais (NF-e/NFC-e) | [apps/notas-fiscais.md](apps/notas-fiscais.md) |
| CFOP | [apps/cfop.md](apps/cfop.md) |
| Transportes (CT-e/MDF-e) | [apps/transportes.md](apps/transportes.md) |
| NFS-e | [apps/nfse.md](apps/nfse.md) |

### Serviços e operação

| App | Documento |
| --- | --- |
| Ordem de Serviço | [apps/ordem-de-servico.md](apps/ordem-de-servico.md) |
| Processos (checklists) | [apps/processos.md](apps/processos.md) |
| Controle de Ponto | [apps/controle-de-ponto.md](apps/controle-de-ponto.md) |

### Plataforma

| App | Documento |
| --- | --- |
| Licenças, planos e trial | [apps/licencas.md](apps/licencas.md) |
| Auditoria | [apps/auditoria.md](apps/auditoria.md) |

### Documentos complementares de módulo

| Documento | Módulos relacionados | Conteúdo |
| --- | --- | --- |
| [apps/precos-promocionais.md](apps/precos-promocionais.md) | Produtos, Caixa, Pedidos, Orçamentos | Fluxo de preços promocionais (à vista / a prazo) |
| [apps/trocas-devolucoes-mapeamento.md](apps/trocas-devolucoes-mapeamento.md) | Trocas e Devoluções | Desenho funcional/técnico e fases de implementação do fluxo |
| [apps/processos-consumo-react-native.md](apps/processos-consumo-react-native.md) | Processos | Consumo da API pelo app mobile: client de exemplo e payloads |

Apps ainda sem documentação padronizada (candidatos a próximos documentos): `Financeiro`, `fiscal`, `sped`, `boletos`, `comissoes`, `contratos`, `dashboards`, `DRE`, `Gerencial`, `GestaoObras`, `marketplace`, `Whatsapp`, entre outros. Utilize o [TEMPLATE.md](TEMPLATE.md).

## Referências externas e notas técnicas

| Documento | Conteúdo |
| --- | --- |
| [referencias-externas/boleto-cora.md](referencias-externas/boleto-cora.md) | Referência da API de boleto registrado da Cora |
| [referencias-externas/boleto-itau.md](referencias-externas/boleto-itau.md) | Referência da API Bolecode Pix do Itaú |
| [referencias-externas/nfe-xml-exemplo.md](referencias-externas/nfe-xml-exemplo.md) | XML de NF-e real para testes do parser |
| [notas-tecnicas/debug-nota-calc-duplicate.md](notas-tecnicas/debug-nota-calc-duplicate.md) | Sessão de debug: `MultipleObjectsReturned` na emissão web |

## Guias de uso do sistema

Guias voltados a usuários e administradores do sistema (não a desenvolvedores), mantidos em `uso/`:

| Documento | Conteúdo |
| --- | --- |
| [uso/cadastro-usuarios-perfis.md](uso/cadastro-usuarios-perfis.md) | Criar usuários, definir setores e configurar perfis de permissão (com telas) |

---

*Estrutura criada em 2026-09-01, consolidando as documentações que estavam espalhadas pelo repositório. Os `README.md` dos apps foram mantidos em suas pastas; a versão padronizada e mantida é a desta pasta. Guias de desenvolvimento ficam na raiz de `docs/`; guias de uso do sistema em `docs/uso/`.*
