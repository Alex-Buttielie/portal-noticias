<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1330-bugs-pendencias/
-->

# Implementation Contract — 20260924-1330-bugs-pendencias

## Metadados
- **run_id:** 20260924-1330-bugs-pendencias
- **Deriva de:** `task-plan.md` (20260924-1330-bugs-pendencias)
- **Versão do contrato:** 1

## O que deve ser construído

### A. Proteção de mídia na variante Caddy
1. Substituir o wildcard público de `/media/*` por uma allowlist equivalente à do Nginx: negar `credenciamento` e descendentes, servir `/media/public/` a partir da raiz correta e fechar caminhos desconhecidos.
2. Manter as rotas de aplicação existentes e os placeholders de domínio; não introduzir domínio real.

### B. Datas civis do Radar
1. No formatador central, reconhecer strings strictly `YYYY-MM-DD` como data civil, sem usar a semântica UTC de `new Date(date-only)`.
2. Preservar o comportamento atual para instantes com hora/fuso e demais entradas aceitas.
3. Tornar o check executável em Node 18/20 sem flags experimentais, com asserções, e registrá-lo no job frontend do CI sob ao menos `TZ=UTC` e `TZ=Asia/Tokyo`.

### C. Correlação e invalidação de cache
1. Sanear `X-Request-ID` no middleware antes de propagá-lo: preservar IDs válidos de até 64 caracteres; para vazio, sentinel, excessivo ou não imprimível, gerar UUID4 válido.
2. Garantir que o mesmo valor final esteja em `request.META`, atributo do request, ContextVar/log, header de resposta e `EventoBusca.request_id`.
3. Invalidar todas as chaves de autocomplete após decisão editorial no painel e após approve/reject ou edição de status no admin nativo, sem transformar falha de cache em erro fatal.

### D. Confirmação de deploy e dependências
1. No job `validate`, capturar o status HTTP da API e da web e promover `.deployed-sha` somente quando ambos forem exatamente 200; 3xx, 4xx, 5xx e erro de conexão (`000`) não contam.
2. Manter as barreiras existentes de resultado do job e SHA verificado.
3. Remover `pytest*` do runtime e do lock de produção; criar `requirements-dev.txt`; fazer CI e bootstrap local instalarem as dependências de teste sem alterar o caminho de deploy.
4. Validar os seis workflows por actionlint, parser YAML com detecção de duplicatas e conferência estrutural dos gates.

## Áreas/arquivos esperados
- `Caddyfile`
- `frontend/lib/datas.ts`
- `frontend/scripts/verificar-datas-tz.mjs`
- `backend/config/middleware.py`
- `backend/config/tests/test_request_id.py`
- `backend/painel_admin/services.py`
- `backend/painel_admin/tests/test_sanity.py`
- `backend/catalogo_noticias/admin.py`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/requirements-lock.txt`
- `backend/.dockerignore`
- `scripts/init-local.ps1`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- documentação diretamente alterada pela execução (`README.md`, `CI-CD.md`, settings auxiliares)
- `agentic-framework/state/run-20260924-1330-bugs-pendencias/implementation-history.md`
- Alterações fora dessa lista precisam ser justificadas no histórico e não podem incluir `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json`.

## Interfaces afetadas
- Caddy: resposta de arquivos privados e caminhos desconhecidos sob `/media/`.
- Formatador de datas do frontend: semântica de entrada date-only civil; instantes com fuso permanecem iguais.
- Header/log/campo `EventoBusca.request_id`: contrato de formato e limite de 64 caracteres.
- Painel/admin: efeito colateral imediato de invalidação de cache ao mudar `status_revisao`.
- Workflow de deploy: condição de promoção de `.deployed-sha`.
- Instalação Python: contrato entre lock runtime, dependências de desenvolvimento, CI, Docker e bootstrap local.

## Critérios de aceite (técnicos, testáveis)
1. Dado um pedido por `/media/credenciamento/<id>/documento.pdf` na variante Caddy, quando a configuração é avaliada, então a rota é negada/404 e não existe fallback que exponha `/srv/media` inteiro.
2. Dado um pedido público por `/media/public/<arquivo>`, quando a configuração é avaliada, então a rota serve a partir de `/srv/media/public` preservando o nome do arquivo.
3. Dado `2026-09-23` como entrada civil, quando o formatador é executado com TZ UTC ou Asia/Tokyo, então a saída é `23/09/2026`; dado `2026-09-23T21:30:00Z`, então a data continua `23/09/2026` e a hora `18:30`.
4. Dado o check de datas, quando executado em Node 18 e Node 20 sob TZ UTC e Asia/Tokyo, então ele falha por asserção se qualquer saída divergir e retorna zero quando todas conferem.
5. Dado um `X-Request-ID` válido de até 64 caracteres, quando uma requisição passa pelo middleware, então ele é preservado; dado valor vazio, `-`, excessivo ou não imprimível, então um UUID4 de até 64 caracteres é gerado.
6. Dado uma requisição com ID normalizado, quando a busca é registrada, então `EventoBusca.request_id` é byte a byte o valor do header de resposta e do request; dois IDs longos distintos geram IDs persistidos distintos.
7. Dado um item pendente já presente nas três chaves de autocomplete, quando ele é aprovado, rejeitado ou tem status editado pelo painel/admin, então as três chaves ficam vazias.
8. Dado um probe que responde 200, 301, 302, 404, 500 ou erro de conexão para API/web, quando o job `validate` avalia o resultado, então somente a combinação API=200 e web=200 pode promover `.deployed-sha`, preservando as demais barreiras.
9. Dado o lock runtime, quando suas dependências são instaladas, então `pytest`, `pytest-django`, `pytest-cov` e `coverage` não estão presentes; dado o manifesto dev + suíte de testes, então o ambiente de teste é funcional e `pip check` passa.
10. Dado o job frontend do CI, quando ele roda na versão Node suportada, então executa o check de datas antes de `tsc`/build sob os fusos definidos.
11. Dado os seis arquivos em `.github/workflows/`, quando são validados, então actionlint e YAML sem chaves duplicadas passam, e a estrutura mantém `verify`, `tls_enabled`, `concurrency` e o gate estrito de rollback.
12. Dado o diff total, quando `git status` é inspecionado, então o run-state modificado por outra sessão está preservado e fora do escopo deste lote.

## Não-objetivos
- Não arquivar `ingestao-service/`, migrar React Query ou mover o build para o runner.
- Não alterar migrations, modelos, endpoints ou payloads.
- Não adicionar biblioteca, chave de cache ou headers HTTP fora do necessário.
- Não validar comportamento em VPS, GitHub Actions real ou DNS/TLS real.
- Não modificar o run-state de outra sessão.

## Restrições técnicas
- **Performance:** invalidação deve ocorrer somente após escrita editorial; o check de datas deve ser leve e não 인상ionar dependências do build de produção.
- **Segurança/privacidade:** fail-closed na mídia privada; IDs não imprimíveis ou excessivos não podem ser propagados/ persistidos; nenhuma credencial em arquivos.
- **Dependências permitidas:** nenhuma nova. Somente `typescript`, já presente no frontend, pode ser usada pelo check de datas.
- **Estilo/convenções:** Python/Django e TypeScript/Next.js conforme padrões existentes; comentários objetivos em português; preservar mudanças anteriores da branch.
- **Revisão:** obrigatória por alterar dados privados/edge, contrato de request ID, efeito em moderação e deploy, além de ultrapassar o limiar de 300 linhas.

## Definição de pronto (Definition of Done)
- [x] Critérios de aceite implementados
- [ ] Testos escritos/validados por tester independente
- [ ] Revisão de código aprovada por reviewer independente
- [ ] Documentação revisada por documenter
- [ ] `implementation-history.md` completo e coerente
- [ ] `report.md` e entrada do historian
