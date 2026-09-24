<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO FOI CRIADO: início da execução 20260924-1535-arquivar-ingestao
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1535-arquivar-ingestao/
-->

# Task Plan — 20260924-1535-arquivar-ingestao

## Metadados
- **run_id:** 20260924-1535-arquivar-ingestao
- **Data de abertura:** 2026-09-24
- **Solicitado por:** humano (Alex), via sessão orquestradora
- **Spec de origem:** decisão explícita do solicitante após a run `20260924-1400-tls-ingestao`; `PROD_DECISOES.md` §7 e `ANALISE_CUSTO_PERFORMANCE.md` §6/§7

## Objetivo
Arquivar definitivamente o segundo pipeline de ingestão FastAPI/Mongo e eliminar a integração opcional do portal, deixando Django/PostgreSQL/Celery como única fonte de verdade executável, com documentação coerente e sem referências operacionais órfãs.

## Escopo
### Dentro do escopo
- Remover todos os arquivos versionados de `ingestao-service/`, incluindo API, pipeline, painel, compose, Dockerfile, requirements e testes.
- Remover `backend/feed/microservice_client.py`, seus testes e os ramos de leitura/sincronização que o condicionavam.
- Remover `MICROSERVICO_INGESTAO_URL`/`INGESTAO_API_TOKEN` de settings, exemplos de ambiente e comentários operacionais.
- Atualizar decisões, arquitetura e documentação de custo para registrar que o microserviço foi arquivado e que o pipeline Django é a única fonte de verdade.
- Verificar que o feed,-playing, robôs, busca, cache, advertising e demais APIs locais continuam funcionando sem chamadas de rede ao serviço removido.
- Preservar integralmente o diretório `backend/`, migrations e a working tree das runs anteriores; não reescrever histórico.

### Fora do escopo (explicitamente)
- Não apagar, migrar ou transformar dados em uma instância MongoDB existente; nenhuma VPS foi acessada.
- Não alterar migrations, modelos, contratos do frontend ou comportamento do pipeline Django além de retirar o caminho alternativo removido.
- Não criar cópia do código em `docs/archive`, conforme a escolha de remoção definitiva.
- Não reescrever relatórios históricos, `HISTORY.md` ou run-state de outra run.
- Não fazer commit, push ou deploy nesta etapa.

## Suposições assumidas
- “Arquivar de vez” significa remover o código do diretório atual e também o adaptador opcional do portal — decisão confirmada explicitamente pelo solicitante.
- O ambiente de desenvolvimento não depende do serviço removido; o defaults já era desligado e o pipeline Django/Postgres é a fonte de verdade.
- O `.env` local/da VPS não será editado automaticamente porque contém configuração operacional; a remoção da flag no exemplo será acompanhada de um follow-up humano para arquivos já existentes.

## Restrições
- Preservar o comportamento público do feed Django, inclusive payloads, cache, paginação, curadoria e `exibir_publicidade` removido dos payloads.
- Não deixar imports, URLs, nomes de settings, caminhos de compose ou comandos que apontem para arquivos removidos.
- Não alterar dados nem apagar volumes Mongo sem acesso e autorização explícita.
- Não incluir segredos, domains ou tokens ao introduzir documentação.
- O diff é deletions + alterações de API/configuração e deve passar por revisão independente.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | remoções, limpeza de referências e implementation-history.md |
| 2 | tester | implementation-contract.md e diff | suíte completa, grep de referências e veredito independente |
| 3 | reviewer (obrigatório: API/comportamento/volume) | diff e contrato | code-review-contract.md |
| 4 | remediator (se necessário) | findings | correções + reteste |
| 5 | documenter | histórico/revisão | documentation-update.md e docs finais |
| 6 | historian | todos os artefatos | report.md + uma linha no HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Não existe mais nenhum arquivo versionado de `ingestao-service/` no repositório e não há comando/serve/compose que tente iniciá-lo.
2. O portal não possui mais caminho alternativo para servir feed, detalhes ou síncronizar fontes no microserviço; todas as leituras e o fluxo de robôs usam exclusivamente Django/Postgres.
3. As flags e referências de configuração do microserviço foram removidas de settings e exemplos, sem quebrar o boot do Django.
4. A documentação explica a decisão, o motivo, o que foi removido e a orientação para operadores que ainda tenham as flags em `.env`/Mongo antigo.
5. A suíte existente continua passando sem os testes do cliente removido, e o build/validações não encontram referências operacionais ao serviço.
6. Nenhum migration, dado de produção, run-state de outra sessão ou registro histórico foi apagado/alterado indevidamente.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Consumidor oculto importar o cliente removido | alto | grep completo, `manage.py check`, suíte e smoke dos endpoints de feed/robôs |
|行为 local do feed mudar ao remover fallback | alto | preservar branches locais, testar endpoints e comparar contratos/lógica antes/depois |
| Configuração antiga em `.env` ficar sem efeito mas confusa | médio | remover do exemplo, documentar limpeza humana sem editar secret files |
| Mongo antigo continuar rodando na VPS | médio | follow-up explícito para desligar/Remover serviço e volume após confirmar backup; não fingir que git remove dados |
| Histórico parecer inconsistente | baixo | não reescrever run-state/relatórios; apenas registrar decisão atual em documentos vivos |
| Remover testes reduzir cobertura | médio | manter testes locais equivalentes, revisar suíte poragmação e exigir gate mínimo |

## Dependências
- Nenhuma dependência externa; a validação usa o ambiente Python/Node já instalado e PostgreSQL real do lote A.
- A removal do Mongo em uma VPS é ação humana posterior, fora deste repositório.
- A run `20260924-1330-bugs-pendencias` e o run-state concorrente `20260924-1400-tls-ingestao` devem permanecer intactos.
