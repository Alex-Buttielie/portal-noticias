<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1330-bugs-pendencias/documentation-update.md
-->

# Documentation Update — 20260924-1330-bugs-pendencias

## Metadados
- **run_id:** 20260924-1330-bugs-pendencias
- **Baseado em:** `implementation-history.md`, no reteste final aprovado e na reconciliação final da revisão

## Documentos afetados

| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` | atualização e correção de contradição | Mantém Python 3.12 como versão coberta; separa manifests de runtime e de testes; corrige a descrição obsoleta que ainda dizia que o Caddy precisava de correção; documenta o contrato fail-closed de mídia, a normalização de `X-Request-ID` e a semântica determinística de datas civis/instantes; remove referências internas de execução da orientação ao desenvolvedor. |
| `CI-CD.md` | atualização operacional | Exige `curl rc=0` e HTTP exatamente `200` para promover `.deployed-sha`; atualiza também o procedimento manual de rollback; descreve o gate de datas em Node 20 nos fusos UTC/Tokyo; explicita os caminhos de `requirements.txt`, lock runtime e manifesto dev; alerta que configuração versionada não prova execução no GitHub Actions/VPS. |
| `infra/DEPLOY.md` | correção de contradição | Substitui o aviso obsoleto que afirmava exposição pelo Caddy pelo contrato testado: subtree privada e caminhos desconhecidos em 404, somente `/media/public/*` servido e nenhum fallback para `/srv/media`; preserva a ressalva de que validação local não comprova implantação na VPS. |
| `backend/.dockerignore` | configuração correlata já alterada, sem nova edição | O diff real exclui `requirements-dev.txt` do contexto Docker. O arquivo foi lido e mantido para garantir que ferramentas de teste não entrem na imagem. |
| `scripts/init-local.ps1` | bootstrap correlato já alterado, sem nova edição | O diff real passa a orientar Python 3.12 e instalar `requirements-dev.txt` no ambiente local. O bootstrap não foi modificado novamente. |
| `agentic-framework/state/run-20260924-1330-bugs-pendencias/documentation-update.md` | novo artefato de fase | Registra documentos, exemplos, ausência de changelog, validações e limitações desta atualização. |

## Sem impacto em documentação?

Não se aplica: houve atualização real em `README.md`, `CI-CD.md` e `infra/DEPLOY.md`. Os manifests, `.dockerignore`, bootstrap e workflows foram apenas conferidos como fonte do comportamento documentado.

## Exemplos/snippets novos ou atualizados

- `README.md` agora mostra o contrato de instalação local com `pip install -r requirements.txt` para runtime e `pip install -r requirements-dev.txt` para testes.
- `README.md` registra os exemplos determinísticos `2026-09-23` → `23/09/2026` e `2026-09-23T21:30:00Z` → `23/09/2026` / `18:30`, sem tratar a data civil como instante UTC.
- `CI-CD.md` substituiu os dois `curl -fsS` do procedimento manual por `probe_http_200`, que exige simultaneamente rc `0` e código `200` antes da promoção do marker.
- `README.md` e `infra/DEPLOY.md` mostram o contrato de mídia: `/media/credenciamento` privado/404, `/media/public/*` público e demais subárvores fechados.

## Entrada de changelog

Não há arquivo `CHANGELOG*` no repositório; nenhuma entrada de changelog foi criada.

## Verificação

- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança.
- [x] Build/lint de documentação: não há Markdown lint/build configurado; os documentos afetados e este artefato foram processados com `markdown-it-py`, sem erro de parsing.
- [x] Busca por placeholders e contradições: nenhuma chave dupla de template permaneceu nos documentos atualizados; expressões operacionais como `${{ inputs.* }}` e placeholders explícitos de domínio em runbooks foram preservados de propósito.
- [x] Busca directional: não há mais, nos documentos ativos atualizados, as afirmações sobre Node 24/`--experimental-strip-types`, Python 3.13+, Caddy ainda expondo toda a mídia ou smoke aceitando 3xx.
- [x] `git diff --check` passou sem whitespace inválido.
- [x] Os blocos Bash/Sh de `CI-CD.md` e `infra/DEPLOY.md` passaram em `bash -n`; a função `probe_http_200` extraita do runbook aceitou 200/rc 0 e rejeitou 302/rc 0, 200/rc 18 e 000/rc 7.

## Limitações e integridade do escopo

- O workflow versionado usa Node 20 no job frontend e executa o check sob `UTC` e `Asia/Tokyo`; Node 18/20 × os dois fusos foi validado em containers locais. A documentação não afirma que o GitHub Actions executou Node 18 nem que houve deploy na VPS.
- Não houve disparo real no GitHub Actions, acesso a VPS, DNS ou TLS; as afirmações operacionais permanecem descritas como contrato versionado e precisam ser observadas no run remoto quando forem exercitadas.
- `ANALISE_CUSTO_PERFORMANCE.md` é uma análise datada de 2026-09-22 e preserva o estado anterior para auditoria; não foi reescrita como runbook atual.
- O SHA-256 preservado de `agentic-framework/state/run-20260924-1400-tls-ingestao/run-state.json` é `7c57ea9bfe8ebe2920247f94aa9d73b9b1efd152a3286b226a8ab20954f5dc4f`; o conteúdo de `agentic-framework/state/loteA-bugs/implementation-history.md` permanece com SHA-256 `16d394a4816725b4edfa95f5a1f052395ffee21a17faa027e265bb0fb0f28889`.
- Nenhum código de produção, workflow, teste, migration ou arquivo em `ingestao-service/` foi alterado nesta fase; nenhum commit foi criado.
