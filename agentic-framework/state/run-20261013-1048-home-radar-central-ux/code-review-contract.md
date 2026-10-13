<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO É CRIADO: sempre que review-triggers.md indicar revisão obrigatória, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract — 20261013-1048-home-radar-central-ux

## Metadados
- **run_id:** 20261013-1048-home-radar-central-ux
- **Escopo revisado:** working tree completa (nada commitado) produzida pelo executor nas Iterações 1-3 (Bloco H/Home, Bloco R/Radar, Bloco C/Central), validada na Iteração 4 pelo tester. `git diff` de todos os arquivos modificados + todos os arquivos novos (`??` em `git status`).
- **Contrato de referência:** implementation-contract.md (20261013-1048-home-radar-central-ux)
- **Gatilhos aplicados (de review-triggers.md):** (a) mudanças em dados de geolocalização do usuário (Bloco R — `lat`/`lon` enviados ao Radar, nova geocodificação textual em `enderecos/services.py`); (b) mudanças em dados pessoais/controle de acesso de usuários (Bloco C — criação/bloqueio/promoção de usuário pelo admin); (c) diff grande (>300 linhas, 17 frentes em 3 blocos).

## Findings

### Finding 1
- **Arquivo:** `backend/radar/views.py` (`TendenciasView`, `NoticiasView`) + `backend/enderecos/services.py` (`resolver_uf`/`_resolver_uf_por_geocoding`)
- **Linha:** `TendenciasView.get` / `NoticiasView.get` (sem `throttle_classes`); chamada a `_resolver_uf_por_geocoding` em `backend/radar/services.py::_resolver_estado`
- **Categoria:** security
- **Severidade:** major
- **Resumo:** As duas views públicas (`AllowAny`) que agora aceitam `estado` como texto livre disparam, para qualquer string que não bata com sigla/nome de UF, uma chamada HTTP de saída ao Nominatim (`_resolver_uf_por_geocoding`) — sem nenhum throttle aplicado. O próprio projeto já tem o mitigante certo para exatamente este padrão (`config.throttling.EnderecosAnonThrottle`, aplicado em TODAS as views de `backend/enderecos/views.py` que tocam upstream externo, com o comentário em `config/settings.py` dizendo literalmente "leitura pública com upstream externo... rajadas batem"), mas ele não foi aplicado às novas views do Radar que entram no mesmo caminho de código.
- **Cenário de falha:** Um cliente anônimo faz requisições repetidas a `GET /api/radar/tendencias/?estado=<string-aleatória-N>` variando a string a cada chamada (o cache de `_resolver_uf_por_geocoding` é por texto exato — md5 do texto normalizado — então strings diferentes nunca batem cache). Cada requisição gera uma chamada de saída real ao Nominatim, sem limite de taxa local. Em volume, isso (i) amplifica uma única requisição barata ao backend do portal em uma chamada de rede ao serviço externo, violando a política de uso aceitável do Nominatim (que exige baixa taxa e cache — a mesma preocupação que já levou `EnderecosAnonThrottle` a existir), com risco de o IP do servidor ser bloqueado pelo Nominatim; (ii) consome o timeout configurado (`_timeout()`) por requisição, degradando o próprio endpoint sob esse tipo de tráfego.
- **Sugestão:** Aplicar `throttle_classes = [EnderecosAnonThrottle]` (ou um throttle equivalente, dedicado) em `TendenciasView` e `NoticiasView` — o mesmo padrão já usado em `backend/enderecos/views.py` para o mesmo tipo de risco.

### Finding 2
- **Arquivo:** `backend/painel_admin/serializers.py` (`UsuarioCriacaoSerializer.validate_email`) + `backend/painel_admin/views.py` (`UsuarioListView.post`) + `backend/identidade/services.py` (`criar_usuario_admin`)
- **Linha:** `UsuarioCriacaoSerializer.validate_email` (checagem `User.objects.filter(email__iexact=normalizado).exists()`) seguida, sem transação/retry, de `criar_usuario_admin(...)` → `user.save()`
- **Categoria:** correctness
- **Severidade:** minor
- **Resumo:** Existe uma janela de corrida (check-then-act) entre a verificação de duplicidade de e-mail na serializer e o `save()` que efetivamente grava o usuário — sem `try/except IntegrityError` nem operação atômica (`get_or_create`/constraint handling), diferente do cuidado já registrado no fluxo público de cadastro (`identidade.views.CadastroView`/`CadastroSerializer`, que documenta explicitamente a preocupação com duplicidade e a resolve de forma mais defensiva).
- **Cenário de falha:** Dois `POST /api/admin/usuarios/` com o mesmo e-mail chegam quase simultaneamente (ex.: duplo-clique acidental no botão "Criar usuário" não bloqueado a tempo, ou dois admins cadastrando a mesma conta por coincidência). As duas chamadas a `validate_email` passam (nenhuma vê a outra ainda commitada); a segunda `user.save()` colide com a constraint `unique=True` de `email` e levanta `django.db.utils.IntegrityError`, não capturada em nenhum lugar do caminho — o admin recebe um 500 genérico em vez do 400 "Já existe uma conta com este e-mail." que o fluxo normal (não-concorrente) devolve.
- **Sugestão:** Envolver a criação em `try/except IntegrityError` (devolvendo o mesmo 400 da validação) ou usar `get_or_create`/`select_for_update` para fechar a janela.

### Finding 3
- **Arquivo:** `frontend/app/noticia/LeituraPremium.tsx` (critério de aceite 4 do contrato)
- **Linha:** N/A (ausência de teste, não de código)
- **Categoria:** test-coverage
- **Severidade:** minor
- **Resumo:** O critério de aceite 4 pede literalmente "contagem de ocorrências do texto no DOM == 1", mas não há teste automatizado que renderize o componente e conte essa ocorrência — a suíte frontend (`node --test`) não tem `@testing-library/react`/jsdom instalados, e nenhuma dependência nova foi adicionada para isso. A garantia atual é só leitura de código (confirmada por mim nesta revisão: `avisoFallback` só é renderizado uma vez, em `d.fontes[0]`, e os outros 4 pontos que repetiam o mesmo texto fixo estão corretamente guardados por `!f.resumo_e_fallback` ou substituídos por frases diferentes) + testes de backend do cálculo da flag (`feed/tests/test_resumo_e_fallback.py`).
- **Cenário de falha:** Uma regressão futura que reintroduza a renderização do texto fixo em um dos pontos já corrigidos (ex.: um novo componente de preview que reusa `d.fontes[0].resumo` sem checar `resumo_e_fallback`) não seria pega por nenhum teste automatizado — só apareceria em inspeção manual da página.
- **Sugestão:** Registrar como item de backlog de hardening de testes (ex. adicionar `@testing-library/react`+jsdom numa run futura, decisão que cabe ao orchestrator por envolver nova dependência de teste) — não bloqueia este run, a lógica atual está correta por leitura completa do código.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 1 |
| minor | 2 |
| nit | 0 |

## Veredito
**changes_requested**

O Finding 1 (major) é um vetor de abuso real e concreto — endpoint público novo sem o throttle que o próprio projeto já usa, por precedente, para exatamente esse tipo de egress externo (geocodificação) — e deve ser corrigido antes de fechar o Bloco R. Os Findings 2 e 3 (minor) não bloqueiam merge, mas devem ser registrados para correção/backlog. Todo o resto do diff (geolocalização nunca persistida em texto claro, `SessaoEgress` usado corretamente, `resolver_uf` nunca inventa UF, auditoria de criação/bloqueio de usuário via `AuditoriaAdmin`, nenhuma senha logada/exposta, gating via `has_feature` preservado, migrações aditivas, `_FRASE_SEM_RESUMO_EDITORIAL`/`verificar_sem_fabricacao` intocados, throttle de `last_seen` corretamente implementado em `services.py` e não no middleware) foi revisado e está correto e alinhado ao contrato.

---

## Segunda rodada de revisão (2026-10-13 — reviewer)

Verificação independente (não é aceitação do relato do remediator) da correção reportada na Iteração 5 de `implementation-history.md`.

### Finding 1 (major) — RESOLVIDO, confirmado

- Lido `backend/radar/views.py`: `TendenciasView` e `NoticiasView` agora declaram `throttle_classes = [EnderecosAnonThrottle]` (import de `config.throttling`), a mesma classe já usada em `backend/enderecos/views.py` para o mesmo risco de egress externo.
- Lido `backend/radar/tests/test_views.py`: os 3 testes novos (`test_tendencias_e_noticias_view_declaram_o_throttle_de_enderecos`, `test_tendencias_view_com_estado_variando_ainda_dispara_429`, `test_noticias_view_com_estado_variando_ainda_dispara_429`, `test_throttle_de_radar_e_por_ip_nao_global`) reproduzem o cenário exato do finding (`estado=` variando a cada chamada, nunca resolvível, nunca bate cache) e usam `LocMemCache` isolado para não depender de Redis.
- **Verificação extra que fiz (não apenas leitura):** monkeypatchei em runtime `TendenciasView.throttle_classes = []` e `NoticiasView.throttle_classes = []` (sem alterar o arquivo em disco — `git status` confirmou nenhuma mudança residual) e re-executei os 2 testes de 429. Ambos **falharam** (200 em vez de 429) nessa condição, confirmando que o teste exercita o throttle real do DRF, não um mock vazio. Restaurado o estado original só saindo do processo Python (nenhum arquivo tocado).
- Rodado `cd backend && .venv/bin/python -m pytest -q radar/ enderecos/ painel_admin/ identidade/` → **335 passed, 0 failed**, igual ao relatado pelo remediator.
- **Decisão sobre `EvolucaoView` (não receber throttle):** avaliada e considerada razoável. `EvolucaoView` exige `IsAuthenticated` + `has_feature(request.user, "radar_avancado")` verificado ANTES de chamar `services.evolucao_interesse` (confirmado por leitura de `backend/radar/views.py:67-80`) — só usuário autenticado Premium chega ao caminho de resolução de `estado`. `EnderecosAnonThrottle` tem base `AnonRateThrottle`, cujo `get_cache_key` do DRF devolve `None` para requisições autenticadas (comportamento padrão do DRF, não específico deste projeto) — aplicá-la ali seria de fato um no-op. Criar uma `UserRateThrottle` dedicada para abuso por usuário Premium autenticado é um risco categoricamente diferente (um usuário Premium cadastrado abusando do próprio limite, não um anônimo variando IP/texto) e extrapolaria o finding original. **Nenhum finding novo aberto aqui.**

### Finding 2 (minor) — RESOLVIDO, confirmado

- Lido `backend/painel_admin/views.py::UsuarioListView.post`: a chamada a `criar_usuario_admin(...)` está envolvida em `try/except IntegrityError`, devolvendo `400 {"email": ["Já existe uma conta com este e-mail."]}` — mesmo formato da validação não-concorrente.
- Lido `backend/identidade/services.py::criar_usuario_admin`: confirmado que a função faz um único `user.save()` sem nenhuma outra escrita com constraint própria — então capturar `IntegrityError` genericamente aqui não mascara um tipo de erro diferente do esperado (o único `IntegrityError` plausível neste caminho é a colisão de `email` unique).
- Lido e executado `backend/painel_admin/tests/test_bloco_c_central_admin.py::test_admin_cria_usuario_colisao_de_corrida_devolve_400_nao_500` isoladamente e dentro da suíte completa → **passou**. O teste usa `patch("painel_admin.views.criar_usuario_admin", side_effect=IntegrityError(...))` para simular a janela de corrida real (a validação da serializer já passou antes da exceção), e confirma 400 + corpo com `"email"` + que a conta não foi criada.

### Finding 3 (minor, test-coverage de DOM) — mantido como follow-up, não bloqueante

Concordo com a decisão do remediator de não resolver agora: instalar `@testing-library/react`/jsdom é introdução de nova dependência de teste (gatilho de `review-triggers.md` — "nova dependência externa"), fora do mandato de uma correção pontual de 2 findings. A lógica do componente já havia sido confirmada correta por leitura de código na primeira rodada. Não bloqueia merge. Registrado para backlog.

### Item 4 — Findings novos desta rodada

Nenhum finding novo (blocker/major/minor) encontrado nas mudanças da correção em si. Pontos verificados e descartados como não-findings:
- `except IntegrityError` em `UsuarioListView.post` é suficientemente específico (único `save()` no caminho, única constraint unique relevante é `email`) — não há cenário concreto de mascaramento de outro erro.
- Decisão de não throttle em `EvolucaoView` é tecnicamente correta (no-op de `AnonRateThrottle` em requisição autenticada é comportamento documentado do DRF) e o risco de abuso por usuário Premium autenticado individual é categoricamente diferente do finding original (abuso anônimo por IP).
- `ParaVoceRegionalView` (AllowAny, aceita `estado`/`cidade` texto livre) foi verificada por leitura de `backend/radar/services.py::para_voce_regional`: filtra em memória por comparação de string exata (`.lower() ==`), **sem** chamar `_resolver_estado`/`resolver_uf` — não entra no caminho de egress ao Nominatim, portanto não está no escopo do Finding 1 e não configura finding novo.

## Resumo quantitativo (final)
| Severidade | Quantidade | Status |
|---|---|---|
| blocker | 0 | — |
| major | 1 | resolvido e confirmado nesta rodada |
| minor | 2 | 1 resolvido e confirmado; 1 aceito como follow-up não bloqueante |
| nit | 0 | — |

## Veredito final
**approve**

Finding 1 (major) e Finding 2 (minor) foram corrigidos e verificados de forma independente nesta segunda rodada (leitura de código + execução da suíte + reprodução ativa da falha ao reverter a correção em runtime, sem tocar arquivos). O Finding 3 (minor, test-coverage de DOM) permanece como follow-up de backlog, deliberadamente fora de escopo por exigir nova dependência de teste — não bloqueia merge. Nenhum finding novo surgiu nas mudanças da correção. Suíte `radar/ enderecos/ painel_admin/ identidade/` com 335 passed, 0 failed — sem regressão.
