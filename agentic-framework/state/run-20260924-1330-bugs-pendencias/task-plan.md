<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO FOI CRIADO: 2026-09-24, após a execução delegada do lote e antes do teste independente
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1330-bugs-pendencias/
-->

# Task Plan — 20260924-1330-bugs-pendencias

## Metadados
- **run_id:** 20260924-1330-bugs-pendencias
- **Data de abertura:** 2026-09-24
- **Solicitado por:** humano (Alex), via sessão orquestradora
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md`, follow-ups das runs `20260923-1600-p2-backend-perf`, `20260924-1000-p2-5-frontend` e `20260924-1200-ops-higiene`, complementados pelo pedido explícito de corrigir todos os bugs e pendências

## Objetivo
Eliminar oito bugs e pendências técnicos já identificados em revisões anteriores, sem alterar migrations, dependências de produto ou a topologia de deploy, e submeter todas as correções a teste e revisão independentes.

## Escopo
### Dentro do escopo
- Impedir que a variante Caddy sirva documentos privados de credenciamento por `/media/`.
- Exibir datas civis `YYYY-MM-DD` do Radar no dia correto, independentemente do fuso do host, sem alterar a conversão de instantes com fuso.
- Normalizar `X-Request-ID` antes de propagá-lo e persistir exatamente o valor validado.
- Invalidar imediatamente o cache de autocomplete ao aprovar, rejeitar ou editar o status de um item pelo painel e pelo admin nativo.
- Promover `.deployed-sha` somente quando API e web responderem HTTP 200, nunca 3xx.
- Tornar o check de datas portátil para Node 18/20 e executá-lo no CI sob múltiplos fusos.
- Separar dependências de desenvolvimento e garantir que ferramentas de teste não entrem no runtime.
- Revalidar de forma cruzada os seis workflows de CI/CD, incluindo gates, TLS, concorrência e rollback.

### Fora do escopo (explicitamente)
- Não remover `ingestao-service/`, migrar componentes para React Query ou mover o build do frontend para o runner; são lotes separados já aprovados para runs próprias.
- Não alterar schema/modelos de banco ou aplicar migrations.
- Não executar deploy, alterar DNS/VPS, emitir certificado ou modificar secrets reais.
- Não criar dependência externa nova.
- Não incluir a modificação concorrente de `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json`, preservada por pertencer a outra sessão.
- Não fazer commit nem push neste lote.

## Suposições assumidas
- Nenhuma. O solicitante aprovou explicitamente o escopo amplo (bugs, otimizações e ajustes de segurança); este run materializa somente a primeira entrega determinística, com as três decisões maiores reservadas para runs próprias.

## Restrições
- Compatibilidade com Node 18/20, Python 3.12 do projeto, SQLite nos testes locais e Postgres no CI.
- O caminho privado de mídia deve continuar acessível apenas pela visão autenticada da aplicação.
- Mudanças de shell em workflow devem passar por actionlint e não podem promover SHA em resposta não-200.
- O valor de `X-Request-ID` retornado, exposto no request e persistido em `EventoBusca` deve ser o mesmo.
- Nenhuma credencial, domínio real ou variável secreta pode ser introduzida.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | prompt detalhado dos oito bugs | correções + implementation-history.md |
| 2 | tester | implementation-contract.md e diff | veredito independente passed/failed/blocked + evidências |
| 3 | reviewer (obrigatório: segurança/API/volume) | diff, contrato e evidência do tester | code-review-contract.md com veredito |
| 4 | remediator (se necessário) | findings abertos | correções + revalidação |
| 5 | documenter | histórico e contrato | documentation-update.md + documentação revisada |
| 6 | historian | todos os artefatos | report.md + linha append-only no HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. A variante Caddy não entrega mais arquivos de credenciamento ou caminhos desconhecidos de `/media/` pelo edge; mídia pública continua disponível.
2. O Radar mostra a data civil recebida, sem voltar um dia, e os demais componentes continuam convertendo corretamente instantes com fuso.
3. IDs de requisição externos arbitrários não causam colisão nem quebram a correlação entre resposta, logs e registro de busca.
4. A decisão editorial de um item não pode continuar suggestionando o título anterior no autocomplete depois de aprovada, rejeitada ou editada.
5. Uma resposta 3xx da aplicação web nunca pode validar uma implantação.
6. Uma regressão de data/fuso é detectada automaticamente no CI em versões Node suportadas.
7. Imagens e processos de produção recebem apenas dependências de runtime; o CI continua capaz de executar a suíte completa.
8. Os seis workflows são sintaticamente e estruturalmente coerentes, sem duplicação de chaves ou quebra dos gates de CI, TLS, concorrência e rollback.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Path matching do Caddy deixar uma variante privada acessível | alto | negar `credenciamento` e todo subtree desconhecido, servindo exclusivamente `/media/public/`; validar config e ordem de match |
| Tratar data como civil quebrar instantes timezone-aware | alto | bifurcar apenas strings date-only e testar data civil + instante em TZ UTC e Asia/Tokyo |
| Sanitizar IDs e perder rastreabilidade | médio | gerar substituto determinístico por requisição e comparar header/request/DB no mesmo teste |
| Invalidação em caminho incompleto do admin | médio | cobrir painel, approve/reject e edição de status no admin nativo |
| Probe shell com quoting/redirect incorreto | alto | capturar somente o código, testar 200/3xx/5xx/000 e rodar actionlint |
| Lock runtime incompleto ou CI sem pytest | alto | instalar lock e dev separadamente, `pip check`, suíte completa e inspeção de que pytest não está no lock |
| Alteração concorrente contaminar o lote | médio | isolar a execução no escopo do run e excluir explicitamente o run-state de outra sessão |

## Dependências
- Docker para validar a configuração real do Caddy; se indisponível, validação sintática equivalente deve ser documentada.
- Dependências locais do backend/frontend já instaladas; nenhum serviço externo é necessário.
- Push/deploy e validação na VPS permanecem ações humanas posteriores ao PR.
