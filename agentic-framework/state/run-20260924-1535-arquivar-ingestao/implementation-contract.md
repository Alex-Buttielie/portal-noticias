<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1535-arquivar-ingestao/
-->

# Implementation Contract — 20260924-1535-arquivar-ingestao

## Metadados
- **run_id:** 20260924-1535-arquivar-ingestao
- **Deriva de:** `task-plan.md` (20260924-1535-arquivar-ingestao)
- **Versão do contrato:** 1

## O que deve ser construído

### A. Remoção do serviço
1. Remover todos os arquivos versionados sob `ingestao-service/` (API FastAPI, routers, pipeline, collectors, painel, Docker/compose, `.env.example`, requirements e testes). Não substituir por código de stub ou cópia inativa.
2. Não remover referências históricas em `agentic-framework/state/`; elas são registro append-only e explicam o estado anterior.

### B. Eliminar o caminho alternativo do portal
1. Remover `backend/feed/microservice_client.py` e `backend/feed/tests/test_microservice_client.py`.
2. Em `backend/feed/views.py`, remover imports, classes de erro, branches `servico_ativo()` e fallbacks remotos, mantendo as views locais, serialização, cache, paginação, gating e todos os endpoints/contratos locais.
3. Em `backend/catalogo_noticias/robos_views.py`, remover a importação do cliente e a sincronização best-effort de fontes; preservar a resposta/erro do fluxo local derobôs.
4. Em `backend/feed/tests/test_p1_feed_cache_indices.py`, remover somente o teste/auxiliadores do caminho remoto, mantendo o teste do cache local de urgentes.

### C. Configuração e operação
1. Remover de `backend/config/settings.py` os blocos `MICROSERVICO_INGESTAO_URL` e `INGESTAO_API_TOKEN`.
2. Remover as mesmas variáveis e comentários de `backend/.env.example`; não editar `backend/.env` nem secrets da VPS.
3. Atualizar o comentário de `.gitignore` que dizia que o diretório removido não tinha `.gitignore` próprio, sem alterar regras de runtime.
4. Não deixar `docker compose`, scripts, PM2, CI ou documentação operacional apontando para o serviço removido.

### D. Documentação da decisão
1. Atualizar `PROD_DECISOES.md` para registrar a decisão humana de arquivamento definitivo, a data, a remoção do adaptador/flags e a orientação de desligar qualquer instância Mongo/serviço em VPS.
2. Atualizar `ARCHITECTURE.md` e, se útil, `ANALISE_CUSTO_PERFORMANCE.md` apenas como documentos vivos para dizer que Django/Postgres/Celery é a única fonte de verdade; não reescrever o histórico das runs.
3. Manter uma explicação do motivo (duplicação, painel não autenticado, Mongo exposto, testes fora do CI, custo) e o que fazer com dados externos.

## Áreas/arquivos esperados
- `ingestao-service/**` — todos os arquivos versionados a remover.
- `backend/feed/microservice_client.py` — remover.
- `backend/feed/tests/test_microservice_client.py` — remover.
- `backend/feed/tests/test_p1_feed_cache_indices.py` — remover somente o bloco de microserviço.
- `backend/feed/views.py` — retirar o caminho remoto, preservar o local.
- `backend/catalogo_noticias/robos_views.py` — retirar sync remota.
- `backend/config/settings.py` — retirar duas settings.
- `backend/.env.example` — retirar flags/comentário.
- `.gitignore` — atualizar comentário.
- `PROD_DECISOES.md`, `ARCHITECTURE.md`, `ANALISE_CUSTO_PERFORMANCE.md` — registrar decisão atual.
- artefatos desta run — `implementation-history.md`, contrato e relatórios.

## Interfaces afetadas
- Feed público passa a ter apenas o contrato Django local; a remoção da alternativa não cria uma nova API pública.
- Robôs deixam de fazer sync remoto de fontes; o endpoint local continua o mesmo.
- Settings `MICROSERVICO_INGESTAO_URL` e `INGESTAO_API_TOKEN` deixam de existir.
- Código removido e testes do cliente não podem continuar sendo importados.
- Dados/volume Mongo fora do repositório não são alterados.

## Critérios de aceite (técnicos, testáveis)
1. Dado `git ls-files ingestao-service`, quando a remoção é concluída, então retorna vazio; e `find ingestao-service` não encontra diretório no repositório.
2. Dado um grep de fontes/configuração exclindo `agentic-framework/state/` e o relatório desta run, quando busca por `microservice_client`, `MICROSERVICO_INGESTAO_URL`, `INGESTAO_API_TOKEN` e `ingestao-service`, então não há referência operacional ativa; referências históricas documentais são permitidas apenas se explicitamente marcadas como histórica.
3. Dado o boot Django, quando `manage.py check` roda, então não há import quebrado e as settings removidas não são exigidas.
4. Dado uma requisição aos endpoints locais de feed, detalhes e urgentes, quando o banco local tem itens, então status/payload/ cache local permanecem corretos sem patching de `requests` ou chamada de rede.
5. Dado a sincronização de fontes dos robôs, quando a operação local é executada, então não há chamada ao microserviço e o fluxo local de persistência/ resposta não sofre ImportError.
6. Dado a suíte de `backend/feed`, quando os testes do cliente removido são descartados, então os testes restantes passam e os testes locais de feed/cache continuam presentes.
7. Dado `docker compose config`/grep de manifests, quando a árvore é validada, então nenhum serviço, volume ou comando do `ingestao-service` é requerido.
8. Dado a documentação viva, quando um operador lê `PROD_DECISOES.md` e `ARCHITECTURE.md`, então encontra a decisão de arquivamento, a fonte de verdade única e a instrução de desligar dados externos sem afirmar que foram apagados.
9. Dado o diff, quando `git diff --check`, YAML/actionlint (se workflows não forem tocados), tsc/build e a suíte PostgreSQL real forem executados, então passam com o gate de cobertura existente; qualquer teste adiciona deve tratar comportamento local, não um stub do serviço removido.
10. Dado o ledger e os run-states anteriores, quando `git status`/histórico são inspecionados, então `HISTORY.md` anterior, relatórios anteriores, `run-20260924-1400-tls-ingestao/run-state.json` e `loteA-bugs/` não foram reescritos.

## Não-objetivos
- Não apagar dados Mongo ou executar comandos de Docker em uma VPS.
- Não migrar o painel `/painel` para o admin Django nesta run; registrar apenas que a capacidade pode ser recriada no Django se necessária.
- Não alterar migrations, modelos, serializers locais, frontend ou performance do pipeline Django.
- Não reescrever `ANALISE_CUSTO_PERFORMANCE.md` como se o achado nunca tivesse existido; apenas registrar o status atual quando apropriado.
- Não criar branch, commit, tag ou release.

## Restrições técnicas
- **Performance:** o caminho local deve continuar usando cache/ETag/bulk_create já entregues; remover uma chamada de rede alternativa não pode introduzir polling.
- **Segurança/privacidade:** eliminar painel sem auth e Mongo publicado do escopo versionado; não expor dados de exemplo ou secrets.
- **Dependências permitidas:** nenhuma nova; requests pode continuar usado pelo Django em outros lugares, mas o adaptador removido não deve deixar dependência órfã específica sem uso.
- **Estilo/convenções:** manter português objetivo, nomes existentes e docs voltadas ao operador; mudanças fora da lista precisam ser justificadas no histórico.
- **Revisão:** obrigatória por alterar comportamento de APIs/configuração, eliminar superfície de segurança e ter grande volume de deleções.

## Definição de pronto (Definition of Done)
- [x] Escopo e decisão de remoção completa definidos
- [ ] Implementação sem referências operacionais órfãs
- [ ] Testes independentes passando
- [ ] Revisão independente aprovada
- [ ] Documentação atualizada
- [ ] Relatório e entrada do historian
