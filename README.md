# BRD Portal de Notícias

Este repositório contém a documentação de negócio (`BRD_portal_noticias_versao_1.docx`) e o **agentic-framework**: a arquitetura de agentes de IA usada para desenvolver este software com um processo consistente de planejamento, implementação, testes, revisão, documentação e histórico auditável.

## Onde começar

- **Requisitos de negócio:** `BRD_portal_noticias_versao_1.docx`.
- **Arquitetura técnica (stack, módulos, modelo de dados, permissões, eventos, integrações):** `ARCHITECTURE.md`.
- **Requisitos técnicos por feature (recorte MVP + Assinatura Premium):** `agentic-framework/specs/` — ver `agentic-framework/specs/README.md`.
- **Código do backend:** `backend/` (Django + Django REST Framework) — ver "Como rodar o backend" abaixo.
- **Código do frontend:** `frontend/` (Next.js + TypeScript) — ver "Como rodar o frontend" abaixo.
- **Como o desenvolvimento é conduzido por agentes de IA:** `agentic-framework/README.md`.
- **Agentes disponíveis (Claude Code):** `.claude/agents/` (`orchestrator`, `executor`, `tester`, `reviewer`, `remediator`, `documenter`, `historian`).
- **Fluxos de trabalho (skills):** `.claude/skills/` (`agentic-run`, `agentic-review`, `agentic-verify`).

## Deploy e infraestrutura

A topologia VPS ativa usa **Gunicorn + PM2 + Nginx**; os runbooks são
`CI-CD.md` e `infra/DEPLOY.md`. O backup da topologia ativa usa
`infra/backup/pg_backup_pm2.sh`; a seção 0 do runbook de infraestrutura cobre
cron, S3 e restore, enquanto `infra/backup/pg_backup.sh` é exclusivo da variante
Docker/Caddy. O Gunicorn usa uma configuração única em
`backend/gunicorn.conf.py`: `worker_class = gthread`, 2 workers × 4 threads e
`timeout = 60` por padrão (ajustáveis por `GUNICORN_*`). O PM2 passa o caminho
absoluto desse arquivo em `--config`, e o timeout pode ser reduzido para 45 s
somente depois que o endpoint 202+background estiver no ref implantado,
alterando Gunicorn e Nginx na mesma mudança.

O Nginx comprime respostas, mantém conexões com o upstream, limita escritas
públicas e usa cache curto de rotas GET públicas. `/static/` e somente
`/media/public/` são servidos diretamente; documentos em
`/media/credenciamento/` **não** têm alias público e continuam disponíveis
somente pela `DocumentoView` autenticada. A ativação dos includes de
cache/rate na VPS segue a ordem include global no `http {}` → snippets/site →
`nginx -t` → reload → restart da API no PM2.

A topologia Docker/Caddy é alternativa, mas seu edge também é fail-closed:
`/media/credenciamento` e seus descendentes retornam 404, somente
`/media/public/*` é servido a partir de `/srv/media/public` e qualquer outro
caminho sob `/media*` é fechado. Assim, a configuração versionada do Caddy não
oferece um fallback para toda a árvore de mídia; consulte `infra/DEPLOY.md`
antes de alterar essa política.

**TLS:** os confs Nginx já suportam HTTPS via Certbot, mas a ativação exige
seguir o runbook em `infra/DEPLOY.md`; produção hoje continua em HTTP até o
certificado ser emitido e `tls_enabled` ser habilitado.

## Inicialização rápida (Windows/PowerShell)

```
.\scripts\init-local.ps1
```

Cria o venv do backend, instala as dependências (Python e Node), gera `backend/.env` e `frontend/.env.local` a partir dos `.example` (com uma `DJANGO_SECRET_KEY` gerada automaticamente e SQLite como banco, para não depender de um PostgreSQL local), roda as migrações e sobe os dois servidores de desenvolvimento em janelas separadas. É idempotente — pode rodar de novo quando quiser sem duplicar trabalho. Use `-SkipStart` para só preparar o ambiente sem subir os servidores, `-DbEngine postgresql` se já tiver um Postgres configurado, ou `-CreateSuperuser` para criar o superusuário do admin na mesma passada. Detalhes de cada passo (e o que fazer manualmente) abaixo.

## Como rodar o backend

Requer Python 3.12. O projeto usa Django + Django REST Framework e, por padrão, PostgreSQL.

1. Crie e ative um ambiente virtual dentro de `backend/`:

   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   # source .venv/bin/activate   # Linux/Mac
   ```

2. Instale as dependências de runtime:

   ```
   pip install -r requirements.txt
   ```

   `requirements.txt` contém as dependências diretas da aplicação;
   `requirements-lock.txt` fixa o mesmo conjunto de runtime e é o arquivo
   usado pelo deploy PM2. `requirements-dev.txt` é exclusivamente para
   desenvolvimento/testes, inclui `requirements.txt` e é usado pelo CI e pelo
   bootstrap local. Não instale o manifesto dev em produção: a imagem Docker
   usa apenas `requirements.txt` e exclui `requirements-dev.txt` pelo
   `.dockerignore`.

3. Copie `backend/.env.example` para `backend/.env` e ajuste os valores (não commite segredos reais):

   - `DJANGO_SECRET_KEY`: gere uma chave própria. Se a aplicação rodar com `DJANGO_DEBUG=false` (padrão) e a `SECRET_KEY` ainda for o valor de exemplo, ela se recusa a subir.
   - `DJANGO_DEBUG`: `true` para desenvolvimento local, `false` em produção.
   - `DJANGO_DB_*`: dados de conexão do PostgreSQL (banco, usuário, senha, host, porta). Você precisa de um servidor PostgreSQL rodando e acessível com essas credenciais.
   - `DJANGO_EMAIL_BACKEND`: em desenvolvimento, o padrão é imprimir os e-mails (inclusive o link/token de verificação e de redefinição de senha) no console em vez de enviá-los de verdade — não há integração com um provedor de e-mail transacional real ainda.
   - `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`: necessários apenas para testar o login social com Google de ponta a ponta; sem eles, os demais endpoints funcionam normalmente.

   Se você não tiver um PostgreSQL disponível para experimentar localmente, é possível apontar para SQLite definindo `DJANGO_DB_ENGINE=sqlite3` — isso não é a configuração recomendada nem o comportamento padrão do projeto, apenas um atalho de conveniência para rodar sem instalar Postgres.

4. Aplique as migrações e suba o servidor:

   ```
   python manage.py migrate
   python manage.py runserver
   ```

   A API fica disponível em `http://localhost:8000/api/`. Há também um painel administrativo Django em `http://localhost:8000/admin/` (crie um superusuário com `python manage.py createsuperuser` para acessá-lo).

5. Para rodar os testes automatizados, instale as ferramentas de desenvolvimento e execute:

   ```
   pip install -r requirements-dev.txt
   pytest
   ```

### Endpoints disponíveis (módulo `identidade`)

Todos abaixo têm prefixo `/api/`.

| Método | Endpoint | O que faz |
|---|---|---|
| `POST` | `/api/auth/cadastro/` | Cria uma conta com e-mail e senha. Exige aceite explícito dos termos de uso. Envia um e-mail (impresso no console em dev) com um token de verificação. |
| `POST` | `/api/auth/verificar-email/` | Confirma o e-mail da conta a partir do token recebido. |
| `POST` | `/api/auth/login/` | Autentica com e-mail e senha e retorna um token de API para as próximas requisições. |
| `POST` | `/api/auth/logout/` | Invalida o token de API do usuário autenticado. |
| `POST` | `/api/auth/recuperar-senha/` | Envia um e-mail com um link/token de redefinição de senha, caso o e-mail informado esteja cadastrado (a resposta é sempre a mesma, para não revelar se o e-mail existe). |
| `POST` | `/api/auth/redefinir-senha/` | Define uma nova senha a partir do token recebido por e-mail. |
| `POST` | `/api/auth/google/` | Login/cadastro com Google: recebe o token de identidade (ID token) obtido no cliente e cria ou associa a conta correspondente. Para uma conta nova, também exige aceite explícito dos termos de uso. |
| `GET` | `/api/onboarding/` | Consulta o estado atual do onboarding do usuário logado (interesses, localidade, canal preferido). Exige conta com e-mail verificado. |
| `PATCH` | `/api/onboarding/` | Atualiza interesses, localidade e/ou canal preferido, ou marca o onboarding como pulado (sem bloquear o uso da conta). Exige conta com e-mail verificado. |
| `GET`/`PUT` | `/api/preferencias-cookies/` | Consulta ou grava a preferência de cookies (categorias `analytics`/`personalizacao`) do usuário autenticado, para sincronizar entre dispositivos — ver "Privacidade e cookies (LGPD)" abaixo. Exige login. |

Detalhes de payload de cada endpoint podem ser consultados diretamente no código em `backend/identidade/serializers.py` e `backend/identidade/views.py`, ou explorados de forma interativa na browsable API do Django REST Framework (acessando as URLs acima pelo navegador com o servidor rodando).

### Endpoints disponíveis (módulo `gating`)

| Método | Endpoint | O que faz |
|---|---|---|
| `GET` | `/api/gating/meus-recursos/` | Matriz de recursos/limites Free x Premium: para cada recurso configurado, mostra o valor aplicável ao plano do usuário e se ele está disponível. Funciona sem login (tratado como plano Free). |
| `GET` | `/api/gating/status/` | Flag `premium_ativo` (público, sem login). É a fonte consumida pelo frontend para decidir exibição de publicidade — os payloads do feed não expõem mais `exibir_publicidade`. Resposta com cache curto (`GATING_CACHE_TTL_SEGUNDOS`, padrão 45s). |

### Endpoints disponíveis (módulo `assinatura`)

| Método | Endpoint | O que faz |
|---|---|---|
| `GET` | `/api/assinatura/planos/` | Lista os planos Premium ativos (público, sem login). |
| `POST` | `/api/assinatura/assinar/` | Assina um plano para o usuário autenticado. |
| `POST` | `/api/assinatura/cancelar/` | Cancela a assinatura ativa (ou em teste) do próprio usuário autenticado. |
| `GET` | `/api/assinatura/minha/` | Consulta a assinatura mais recente do usuário autenticado (status, plano, datas). |
| `GET` | `/api/assinatura/historico-pagamentos/` | Lista o histórico de pagamentos do próprio usuário autenticado. |

### Endpoints disponíveis (módulo `credenciamento`)

| Método | Endpoint | O que faz |
|---|---|---|
| `POST` | `/api/credenciamento/solicitar/` | Envia uma solicitação para se tornar jornalista credenciado (dados profissionais + documento comprobatório em anexo). Bloqueia nova solicitação enquanto houver uma pendente. |
| `GET` | `/api/credenciamento/minha-solicitacao/` | Consulta a solicitação mais recente do usuário autenticado e seu status (pendente, aprovado, reprovado, informação adicional solicitada). |
| `GET` | `/api/credenciamento/solicitacoes/<id>/documento/` | Baixa o documento enviado na solicitação. Só o próprio solicitante ou um admin pode acessar. |
| `GET`/`PATCH` | `/api/credenciamento/meu-perfil/` | Consulta/edita o perfil profissional público do jornalista já aprovado (só existe depois da aprovação). |

### Endpoints disponíveis (módulo `comunidade`)

| Método | Endpoint | O que faz |
|---|---|---|
| `GET`/`POST` | `/api/comunidade/publicacoes/` | Lista publicações já publicadas (filtros `destaque`, `autor`), público. Criar (`POST`) exige login e ser jornalista credenciado — cria um rascunho. A listagem aceita `page`/`page_size` (padrão 20, máximo 100) e, quando explicitamente paginada, retorna o envelope `count`/`next`/`previous`/`results`. |
| `GET`/`PATCH` | `/api/comunidade/publicacoes/<id>/` | Detalhe de uma publicação (rascunho só visível ao próprio autor) / edição do conteúdo pelo autor. |
| `POST` | `/api/comunidade/publicacoes/<id>/enviar/` | O autor envia o próprio rascunho para publicação. |
| `GET`/`POST` | `/api/comunidade/comentarios/` | Lista comentários de uma publicação ou notícia (filtros `publicacao`, `news_item`), público. Criar exige login; suporta resposta a outro comentário. A paginação explícita usa os mesmos limites (`page`/`page_size`, padrão 20, máximo 100) e o envelope paginado. |
| `POST`/`DELETE` | `/api/comunidade/autores/<id>/seguir/` | Segue/deixa de seguir um autor (exige login). |
| `GET` | `/api/comunidade/autores/<id>/perfil/` | Perfil público de um autor: se é jornalista credenciado, número de seguidores e suas publicações. |
| `POST` | `/api/comunidade/denunciar/` | Denuncia um comentário ou publicação (exige login). |

### Endpoints disponíveis (módulo `moderacao`)

| Método | Endpoint | O que faz |
|---|---|---|
| `GET` | `/api/moderacao/fila/` | Fila de denúncias pendentes de análise. Só moderador/admin. |
| `POST` | `/api/moderacao/denuncias/<id>/resolver/` | Resolve uma denúncia (procedente ou não). Só moderador/admin. |
| `POST` | `/api/moderacao/acoes/` | Aplica uma ação de moderação (ex.: advertência, suspensão) a um usuário, sempre com um moderador/admin como decisor humano explícito. |
| `POST` | `/api/moderacao/acoes/<id>/recurso/` | O próprio usuário atingido por uma ação recorre dela. |
| `GET` | `/api/moderacao/paginas/<slug>/` | Página pública de conteúdo editorial (ex.: política de moderação), por slug. |
| `GET` | `/api/moderacao/minha-reputacao/` | Pontuação e nível de reputação do usuário autenticado. |

### Endpoints disponíveis (módulo `radar`)

| Método | Endpoint | O que faz |
|---|---|---|
| `GET` | `/api/radar/tendencias/` | Tendências de notícias por localização (parâmetros opcionais `pais`, `estado`, `cidade`). Público. |
| `GET` | `/api/radar/evolucao/` | Evolução histórica do interesse por categoria/localidade. Recurso Premium (exige login e o recurso `radar_avancado` liberado no plano). |
| `GET`/`POST`/`DELETE` | `/api/radar/localidades-salvas/` | Lista, salva ou remove localidades acompanhadas pelo usuário autenticado. |

### Endpoints disponíveis (módulo `newsletter`)

| Método | Endpoint | O que faz |
|---|---|---|
| `POST`/`DELETE` | `/api/newsletter/inscrever/` | Inscreve (com tipo, categorias e periodicidade) ou cancela a inscrição do usuário autenticado na newsletter. |
| `POST` | `/api/newsletter/descadastrar/` | Descadastro por token (recebido no e-mail da newsletter), sem exigir login. |

### Endpoints disponíveis (módulo `landing`)

| Método | Endpoint | O que faz |
|---|---|---|
| `POST` | `/api/landing/lista-espera/` | Cadastra um interessado na lista de espera (nome, e-mail, interesses, localidade, canal preferido, com consentimento de comunicação). Público, sem login. |

A segmentação dos cadastros na lista de espera (por localidade, busca por nome/e-mail) é feita hoje pelo painel administrativo Django (`http://localhost:8000/admin/landing/inscricaolistaespera/`) — não é um endpoint de API separado.

### Endpoints disponíveis (módulo `b2b`)

| Método | Endpoint | O que faz |
|---|---|---|
| `GET`/`POST` | `/api/b2b/criterios/` | Lista/cria critérios de monitoramento (empresa, concorrente, setor, palavra-chave) da organização do usuário autenticado. |
| `GET` | `/api/b2b/itens-monitorados/` | Notícias que casam com os critérios de monitoramento da organização. |
| `GET` | `/api/b2b/resumo-executivo/` | Painel resumido para a organização (visão executiva do que está sendo monitorado). |
| `GET`/`POST`/`DELETE` | `/api/b2b/membros/` | Lista membros da organização, convida um usuário existente por e-mail, ou remove um membro. |

Em todos os endpoints de `b2b`, a organização é sempre determinada a partir do usuário autenticado (nunca de um id na URL ou no corpo da requisição) — quem não pertence a nenhuma organização recebe 403.

### Endpoints disponíveis (módulo `metricas`)

| Método | Endpoint | O que faz |
|---|---|---|
| `GET` | `/api/metricas/painel/` | Painel agregado de métricas do produto (parâmetro opcional `dias`, padrão 30) — cadastros, assinaturas, gasto com LLM, etc. Só admin. |

## Como popular o feed com notícias reais (ingestão)

A ingestão consulta cada fonte RSS de forma incremental: quando há `ETag`/`Last-Modified` válidos, envia `If-None-Match`/`If-Modified-Since` e trata um `304` sem baixar nem parsear o XML. Os validators só são confirmados depois que o lote foi persistido com segurança; periodicamente a fonte é revalidada sem headers para recuperar o acervo caso o `304` não reflita o estado local. Isso reduz banda e tempo de ingestão sem transformar o validator em prova de completude do acervo.

O pipeline de ingestão (`backend/catalogo_noticias/`) busca notícias de verdade nos feeds RSS configurados em `settings.CATALOGO_NOTICIAS_FONTES_RSS` (G1, UOL, CNN Brasil, Folha — `config/settings.py`), deduplica/agrupa acontecimentos cobertos por várias fontes, gera um resumo próprio via `SummarizationProvider` e classifica categoria/urgência.

1. Com o backend configurado (`.env` + `migrate` já feitos), rode uma execução manual do pipeline a qualquer momento, sem precisar de Celery/Redis:

   ```
   cd backend
   .\.venv\Scripts\python.exe manage.py ingerir_noticias
   ```

   Isso busca os feeds agora mesmo e imprime um resumo (itens novos por fonte, grupos formados, erros de fonte, se houver).

2. **Sem uma `CATALOGO_NOTICIAS_LLM_API_KEY` real configurada em `backend/.env`**, os itens são ingeridos normalmente (título, URL, fonte, conteúdo bruto — tudo real), mas como o resumo automático falha, todo item novo cai em `status_revisao=pendente` e **não aparece no feed público** (`/api/feed/`) — só na fila de revisão do admin (`http://localhost:8000/admin/catalogo_noticias/newsitem/`, filtro "Status revisão = Pendente"). Para validar o fluxo completo (resumo automático + classificação + publicação direta de itens de baixa relevância), é preciso uma chave de API real de um provedor compatível com o formato "Chat Completions" (OpenAI, Groq, OpenRouter, Azure OpenAI, um modelo local via Ollama/vLLM em modo compatível, etc. — `CATALOGO_NOTICIAS_LLM_API_BASE_URL`/`_MODEL` também são configuráveis). Preencha `CATALOGO_NOTICIAS_LLM_API_KEY` em `backend/.env` e rode o comando de novo.
3. Enquanto isso, dá para validar o resto do sistema sem a chave de LLM: aprove manualmente alguns itens da fila do admin (ação em massa "Marcar selecionados como aprovado") para vê-los aparecer no feed público mesmo sem resumo automático.
4. Rodar de novo o mesmo comando é seguro (idempotente) — URLs já ingeridas não são reprocessadas; só notícias novas publicadas pelas fontes desde a última execução entram.
5. Em produção (ou se quiser automatizar localmente), a mesma lógica roda periodicamente via Celery Beat (`CELERY_BEAT_SCHEDULE` em `config/settings.py`, intervalo em `CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS`) — exige um Redis local rodando (`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` em `.env`). A task de ingestão e a task de registro de `EventoBusca` são configuradas por task para reentrega segura; as demais tasks com efeitos externos mantêm o comportamento padrão.

   ```
   cd backend
   .\.venv\Scripts\celery.exe -A config worker -l info
   .\.venv\Scripts\celery.exe -A config beat -l info
   ```

   (em duas janelas separadas; não é necessário para só validar funcionalidades manualmente com o comando `ingerir_noticias` acima.)

### Saúde das filas: `manage.py saude_filas` (P1-03)

O worker e o beat são serviços que "no ar" não provam nada: um beat que
subiu e não disparou nada produz o mesmo `ps` de um beat saudável. Por isso
existe um relatório que **mede** em vez de deduzir:

```
cd backend
.venv/bin/python manage.py saude_filas            # resumo legível
.venv/bin/python manage.py saude_filas --json     # uma linha, para monitor
```

Ele verifica cinco dependências separadamente — registro das tasks da
agenda, broker (profundidade da fila), worker vivo (`inspect().ping()` +
idade da task em execução mais antiga), heartbeat do beat e último ciclo da
task monitorada (`FILAS_TAREFA_MONITORADA`, por padrão a ingestão) — e
devolve **três** estados, com **três códigos de saída distintos**:

| estado | saída | quando |
|---|---|---|
| `ok` | 0 | tudo foi verificado e nada está com problema |
| `degradado` | 1 | algo foi medido e está ruim (fila funda, beat velho, task travada, último ciclo em falha) |
| `desconhecido` | 3 | **não foi possível verificar** |

`desconhecido` existe porque "não consegui medir" e "está tudo bem" são
fatos diferentes, e um monitor que trata os dois como sucesso é um falso
verde. Nenhum caminho de "não medi" converge para `ok`: broker fora do ar,
`inspect()` sem resposta, contagem não numérica, arquivo de estado
ausente/corrompido/sem carimbo e modo inline (em que não existe fila) são
todos `desconhecido`, com o motivo escrito no relatório. Só um fato negativo
**medido** promove a `degradado` — e mesmo aí `verificado` continua `false`.

O **heartbeat do beat** é o que fecha a lacuna entre "processo no ar" e
"agenda rodando": a task `config.tasks.heartbeat_beat` está no
`CELERY_BEAT_SCHEDULE` (chave `portal-heartbeat-beat`, a cada
`FILAS_HEARTBEAT_INTERVALO_SEGUNDOS`, padrão 5 min) e grava em disco, de
cada execução, o instante e o pid de quem rodou. Ela é despachada pelo beat
e executada por um **worker**, então o arquivo só existe se as duas pontas
estiverem de pé. A idade vem do carimbo **dentro** do arquivo, nunca do
`mtime` — um `touch`/`cp -p` externo não fabrica frescor. Passado
`FILAS_BEAT_MAX_AGE_SEGUNDOS` (padrão 900 s, três intervalos) sem novo
registro, o estado vira `degradado` com a idade no motivo.

Onde o estado fica gravado é `PORTAL_FILAS_ESTADO_DIR`; sem essa variável o
padrão é `$XDG_STATE_HOME/portal-noticias` ou um diretório próprio no
tempdir — **nunca dentro do repositório**. Em DEV/HOMOLOG/PROD aponte para um
caminho durável e fora do diretório de deploy (ex.: `/var/lib/portal-noticias`),
criado e com permissão de escrita para o usuário do serviço: sem isso o
diretório some a cada reboot e o relatório volta (corretamente) para
`desconhecido` até o primeiro tick pós-boot. Esse provisionamento é
dependência humana de P0-07, não algo que o código resolva.

**Retry e idempotência da ingestão.** `catalogo_noticias.tasks.ingerir_noticias`
usa `autoretry_for` com uma lista estreita de falhas *transitórias de
infraestrutura* (`django.db.OperationalError`, `redis.exceptions.ConnectionError`
e `TimeoutError`), `max_retries=3`, backoff exponencial com jitter. Erro de
conteúdo de uma fonte não entra nessa lista: ele já é capturado por fonte
dentro de `executar_ingestao` e vira `RegistroExecucaoIngestao.erros_por_fonte` —
um RSS fora do ar não deve reprocessar a ingestão inteira. O número de
tentativas é observável no log e no estado durável (`tentativas_observadas`,
zerado por um sucesso). Reprocessar não duplica: `NewsItem.url_fonte_original`
é `UNIQUE` e a persistência em lote filtra o que já existe antes de escrever,
de modo que uma execução que grava e só depois falha, seguida de retry,
deixa itens, clusters **e custo de LLM** exatamente iguais.

**Modo inline (desenvolvimento, atalho explícito).** `CELERY_TASK_ALWAYS_EAGER=true`
faz `.delay()` executar no próprio processo. É opt-in e **não é o default**,
porque um default inline esconderia a fila justamente no ambiente onde ela
importa. Nesse modo o `saude_filas` responde `desconhecido` para as sondagens
de fila — com o motivo explícito — em vez de fingir que uma fila saudável foi
observada.

### Reduzindo custo/número de chamadas ao provedor de LLM

Por padrão, o pipeline resume os itens novos de uma execução em **lotes** de `CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE` (padrão 10) — uma única chamada HTTP cobre até 10 notícias independentes, em vez de uma chamada por notícia. Cada notícia continua recebendo um resumo gerado exclusivamente a partir do seu próprio conteúdo (nenhum resumo é compartilhado/combinado entre notícias diferentes — a mesma garantia contra atribuição incorreta de conteúdo de antes, só que aplicada a N itens por chamada). Dois parâmetros em `backend/.env` controlam isso:

- `CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE`: quantas notícias por chamada. Um valor maior reduz ainda mais o número de chamadas, mas se a chamada inteira falhar (rede, resposta malformada), todas as notícias daquele lote caem juntas na fila de revisão humana em vez de só uma.
- `CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM`: teto de tokens de resposta por notícia (padrão 220), multiplicado pelo tamanho do lote — evita pagar por respostas mais longas que o necessário para um resumo curto.

Depois de uma execução, o campo "Chamadas summarization provider" de cada `RegistroExecucaoIngestao` (`http://localhost:8000/admin/catalogo_noticias/registroexecucaoingestao/`) mostra quantas chamadas HTTP reais foram feitas — é o número que comprova a redução (ex.: 30 notícias novas viram 3 chamadas com o lote padrão de 10, em vez de 30).

### Teto de gasto diário com o provedor de LLM

Cada chamada ao provedor de resumo tem seu custo estimado a partir dos tokens efetivamente consumidos, multiplicados por um preço configurável em `backend/.env`:

- `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` (padrão `0.0003`): estimativa de custo em dólares por 1000 tokens (entrada + saída somados). É uma estimativa — não a tabela de preços exata de nenhum provedor específico. O padrão é o preço blended conservador do `gpt-4o-mini` (entrada $0.15/1M + saída $0.60/1M; um lote típico de 10 itens ≈ 5000 tokens de entrada + 2200 de saída ≈ $0.00029/1k, arredondado para cima). Com esse padrão, o teto de $5/dia cobre cerca de 16 milhões de tokens por dia. Ajuste esse valor para refletir o preço real do provedor de LLM escolhido.
- `CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD` (padrão `5.0`): teto de gasto diário, em dólares. Assim que o gasto estimado acumulado do dia corrente atinge esse valor, a ingestão **para de chamar o provedor de LLM** pelo restante do dia — as notícias continuam sendo buscadas e ingeridas normalmente, só sem resumo automático: caem na mesma fila de revisão humana do admin usada quando o resumo automático falha por outro motivo (`status_revisao=pendente`). Nenhuma notícia é descartada ou trava a ingestão por causa do teto.

O gasto acumulado do dia (e se o teto já foi atingido) pode ser consultado sem precisar olhar o banco diretamente, no painel de métricas (`GET /api/metricas/painel/`, autenticado como admin): os campos `custo_llm_hoje_usd`, `teto_llm_diario_usd` e `teto_llm_excedido_hoje` mostram, respectivamente, o gasto estimado já feito hoje, o teto configurado e se ele já foi ultrapassado.

> **Nota operacional:** instalações que já têm uma linha `ConfiguracaoRobo` persistida no banco mantêm o valor antigo de `llm_preco_por_1k_tokens` (`0.15`) até ajuste manual via tela admin de robôs — o default novo (`0.0003`) só vale para instalações sem override no banco.

### Eventos de busca e rate limiting

A busca pública responde sem inserir `EventoBusca` no request: `registrar_busca` despacha `feed.tasks.registrar_evento_busca` com payload JSON primitivo, preservando consulta, resultados, filtros, usuário, sessão e `request_id`. O `EventoBusca` é persistido no worker; quando há `request_id`, a task é idempotente para não duplicar a métrica em uma reentrega. A falha de enfileiramento é apenas registrada (métrica best-effort), sem criar uma escrita síncrona no caminho de leitura.

Todo request HTTP tem o `X-Request-ID` normalizado antes de entrar nas views. Um valor aceito é imprimível, não vazio depois da remoção apenas de espaços ASCII nas pontas, diferente de `-` e tem no máximo 64 caracteres; ele é preservado sem truncamento. Valor ausente, vazio, sentinel, excessivo ou não imprimível recebe um UUID4. O mesmo valor normalizado aparece no header de resposta, no request/log e em `EventoBusca.request_id`, mantendo a correlação de ponta a ponta.

O rate limiting continua aplicado somente às escritas públicas anônimas e usa o cache Redis; essa seção não limita os GETs de leitura. Assim, a resposta de busca não espera por broker nem por uma escrita de métrica, enquanto a proteção contra abuso permanece no mesmo ponto documentado abaixo.

## Como rodar o frontend

Requer Node.js 18 ou 20. O projeto usa Next.js 14 (App Router) + TypeScript + **Tailwind CSS 3.4.17** + **shadcn/ui v4 (Radix)** — 5 skills 100% em runtime real via `.claude/skills/frontend-portal/SKILL.md`. Tokens CSS `--cor-*`/`--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*` mapeados em `frontend/tailwind.config.ts` (`theme.extend.colors: var(--cor-*)`, `darkMode: '[data-theme="dark"]'` casando o anti-flash de `layout.tsx`); helper `cn` (`clsx`+`tailwind-merge`) em `frontend/lib/utils.ts`; `frontend/app/globals.css` com `@tailwind base/components/utilities` + `@layer base`; `components.json` (`new-york`, `cssVariables`, aliases) + `tailwindcss-animate`/`class-variance-authority`/`lucide-react`/`@radix-ui/*`.

1. Instale as dependências:

   ```
   cd frontend
   npm install
   ```

2. Copie `frontend/.env.local.example` para `frontend/.env.local` e ajuste se necessário (por padrão já aponta para `http://localhost:8000`, o backend local).

3. Com o backend rodando em outro terminal (`python manage.py runserver`, porta 8000), suba o frontend:

   ```
   npm run dev
   ```

   A aplicação fica disponível em `http://localhost:3000`.

4. **Importante:** o backend precisa ter `django-cors-headers` instalado (`pip install -r requirements.txt` de novo, se você já tinha o `venv` criado antes desta dependência ser adicionada) — sem isso, o navegador bloqueia as chamadas do frontend para a API por política de CORS.

### Páginas disponíveis

| Rota | O que faz |
|---|---|
| `/` | Feed de notícias — busca, filtro por categoria, paginação |
| `/noticia/cluster/[id]`, `/noticia/item/[id]` | Detalhe de um acontecimento, com todas as fontes |
| `/cadastro` | Criar conta |
| `/login` | Entrar |
| `/verificar-email` | Confirma o e-mail (aberta a partir do link enviado por e-mail) |
| `/recuperar-senha`, `/redefinir-senha` | Fluxo de senha esquecida |
| `/onboarding` | Interesses, localidade e canal preferido (exige e-mail verificado) |
| `/planos` | Planos Premium disponíveis e assinatura |
| `/minha-conta` | Status da assinatura, histórico de pagamentos, cancelamento |
| `/lista-de-espera` | Cadastro na lista de espera (nome, e-mail, interesses, localidade), para quem ainda não tem conta |
| `/jornalista/solicitar` | Formulário de solicitação de credenciamento como jornalista (dados profissionais + upload do documento comprobatório) |
| `/jornalista/status` | Status da própria solicitação de credenciamento (em análise, aprovado, reprovado, informação adicional solicitada) e, uma vez aprovado, edição do perfil profissional público |
| `/comunidade` | Lista de publicações (opinião/análise) de jornalistas credenciados, com destaques editoriais |
| `/comunidade/nova` | Criação de um rascunho de publicação e envio para publicação (exige login como jornalista credenciado) |
| `/comunidade/[id]` | Detalhe de uma publicação, comentários e edição pelo próprio autor |
| `/autor/[id]` | Perfil público de um autor (jornalista credenciado): seguidores, seguir/deixar de seguir, lista de publicações |
| `/radar` | Tendências de notícias por localização, evolução histórica (recurso Premium) e localidades salvas |
| `/empresa` | Painel B2B da organização: critérios de monitoramento, itens monitorados, resumo executivo e gestão de membros |
| `/admin/metricas` | Painel agregado de métricas do produto (só admin) |
| `/paginas/[slug]` | Páginas de conteúdo editorial publicadas pelo admin (ex.: política de moderação), por slug |
| `/privacidade/politica` | Política de privacidade — rascunho funcional, ainda não revisado juridicamente |
| `/privacidade/preferencias-cookies` | Gerenciamento de preferências de cookies |

Não construído ainda: login social (Google) na interface (o endpoint de backend existe, mas nenhuma tela chama o fluxo do Google).

## SEO técnico

O frontend gera metadata, dados estruturados e os arquivos técnicos que buscadores e redes sociais esperam, usando só recursos nativos do Next.js (App Router) — sem biblioteca de terceiros.

- **Metadata (título, descrição, Open Graph, Twitter Card):** cada rota de conteúdo (artigo em `/noticia/item/[id]` e `/noticia/cluster/[id]`, autor em `/autor/[id]`) exporta uma função `generateMetadata` (Server Component) que monta `<title>`, `<meta description>`, Open Graph (`og:title`, `og:description`, `og:image`, `og:type`) e Twitter Card a partir do próprio conteúdo. O layout raiz (`frontend/app/layout.tsx`) define os valores padrão herdados por todas as páginas (nome do site, imagem padrão, `metadataBase`) a partir de `frontend/lib/site.ts`.
- **Dados estruturados (JSON-LD, schema.org):** `frontend/lib/schema.ts` tem os construtores prontos (`organizationJsonLd`, `personJsonLd`, `newsArticleJsonLd`, `breadcrumbListJsonLd`, `imageObjectJsonLd`) e `frontend/components/JsonLd.tsx` é o componente que os renderiza como `<script type="application/ld+json">` (com escaping seguro). A página de artigo injeta `NewsArticle` (com `ImageObject` embutido) e `BreadcrumbList`; a página de autor injeta `Person`; o layout raiz injeta `Organization` em toda página.
- **Canonical:** toda página de conteúdo define `alternates.canonical` dentro do próprio `generateMetadata`/`metadata`.
- **`sitemap.xml`, `robots.txt`, `rss.xml`:** `frontend/app/sitemap.ts` e `frontend/app/robots.ts` são gerados dinamicamente pelo Next.js e ficam acessíveis em `/sitemap.xml` e `/robots.txt`; o feed RSS 2.0 fica em `/rss.xml` (`frontend/app/rss.xml/route.ts`). Os três consomem a API pública de notícias (`/api/feed/`) para listar o conteúdo publicado mais recente.

**Como estender isso em uma página nova:** se a página for um Server Component, exporte `generateMetadata` retornando pelo menos `title`, `description` e `alternates.canonical`; para incluir dados estruturados, importe o construtor relevante de `frontend/lib/schema.ts` (ou crie um novo, seguindo o mesmo padrão) e renderize `<JsonLd data={...} />` no corpo da página. Se a página precisar ser um Client Component (interatividade logo de cara), siga o padrão já usado em `frontend/app/autor/[id]/page.tsx`: um `page.tsx` Server Component fino, só com `generateMetadata` e JSON-LD, que renderiza um componente `*Conteudo.tsx` separado marcado `"use client"` — `generateMetadata` não pode ser exportado por um Client Component.

**Limitação conhecida:** como o conteúdo do catálogo de notícias é agregado de fontes externas (sem imagem própria nem autor jornalista individual), `NewsArticle.image`/`og:image` usam uma imagem padrão (`frontend/public/og-padrao.svg`, um rascunho — ainda não é uma peça de design finalizada) e `NewsArticle.author` é a organização do portal, não uma pessoa, mantendo o nome da fonte original em `citation`.

## Privacidade e cookies (LGPD)

> **A política de privacidade (`/privacidade/politica`) é um rascunho funcional, não uma peça jurídica validada.** O aviso está escrito na própria página. Não trate esse texto como definitivo antes de uma revisão jurídica real.

- **Banner de consentimento** (`frontend/components/BannerConsentimentoCookies.tsx`): aparece para qualquer visitante sem escolha registrada, com três opções — "Aceitar todos", "Recusar não essenciais" e "Gerenciar preferências" (painel com um toggle por categoria; a categoria "essenciais" é sempre ativa e não pode ser desligada). A escolha fica salva em `localStorage` e vale para as próximas visitas — o banner não reaparece depois de uma resposta.
- **Nenhum cookie não essencial antes do consentimento:** qualquer script de analytics ou personalização deve checar `permiteCategoria("analytics")`/`permiteCategoria("personalizacao")` (`frontend/lib/cookie-consent.ts`) antes de inicializar. Por padrão, sem resposta registrada, `permiteCategoria` retorna `false` (nega por padrão) — essa é a regra a seguir sempre que um script de terceiros for adicionado no futuro.
- **AdSense/publicidade:** o script do Google AdSense só é carregado após consentimento em `personalizacao`; o componente reage a mudanças de preferência e usa `lazyOnload`, enquanto os slots permanecem placeholders antes da autorização.

  ```ts
  import { permiteCategoria } from "@/lib/cookie-consent";

  if (permiteCategoria("analytics")) {
    // só aqui é seguro inicializar um script de analytics
  }
  ```

- **Página de gestão de preferências** (`/privacidade/preferencias-cookies`): permite revisitar e alterar a escolha a qualquer momento, com link fixo no rodapé do site.
- **Sincronização entre dispositivos (usuário autenticado):** além do `localStorage`, a preferência de um usuário logado é replicada no backend via `GET`/`PUT /api/preferencias-cookies/` (app `identidade`). Ao fazer login (ou ao restaurar uma sessão já autenticada), o frontend importa a preferência já salva na conta para o dispositivo atual — assim a escolha feita em um dispositivo aparece também nos demais.
- **Backend (`backend/identidade/`):** essa foi a primeira funcionalidade do app `identidade` a ganhar uma camada de serviço própria (`identidade/services.py`, antes inexistente) — `atualizar_preferencias_cookies(user, categorias)` é o único ponto que grava esse dado, mantendo a mutação fora da view.

## Rate limiting

Os endpoints públicos de escrita mais expostos a abuso automatizado (`POST /api/auth/cadastro/`, `POST /api/landing/lista-espera/`, `POST /api/comunidade/publicacoes/`) têm um limite de requisições anônimas configurado via DRF throttling (`backend/config/throttling.py`, classe `EscritaPublicaAnonThrottle`). Passado o limite, a API responde `429 Too Many Requests`. Usuários autenticados não são afetados por esse limite.

- **Taxa configurável:** `DEFAULT_THROTTLE_RATES["escrita_publica"]` em `backend/config/settings.py`, lida da variável de ambiente `THROTTLE_ESCRITA_PUBLICA_RATE` (padrão `20/min`) — ajustável sem alterar código.
- **Depende de um cache funcional para valer de verdade:** o throttle guarda a contagem de requisições no mesmo cache Redis usado pelo resto da aplicação. Se o Redis cair, a aplicação continua no ar (degradação graciosa deliberada), mas o rate limiting para de funcionar até o Redis voltar — nesse cenário, a falha de conexão agora gera um log de nível `ERROR` (logger `django_redis.cache`, via `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True` em `settings.py`) em vez de ser engolida em silêncio, então essa degradação fica visível nos logs da aplicação.

## Observabilidade (Sentry opcional)

- **Backend:** `sentry-sdk==2.19.2` já instalado; só inicializa se `SENTRY_DSN` estiver definida (`backend/config/settings.py` + `backend/.env.example`). Sem DSN custo zero.
- **Frontend:** `frontend/sentry.client.config.ts` e `frontend/sentry.server.config.ts` usam `require("@sentry/nextjs")` dinâmico dentro de `if (dsn)` — build não quebra sem o pacote. Para ativar: `npm i @sentry/nextjs` + `NEXT_PUBLIC_SENTRY_DSN` (ou `SENTRY_DSN` no server) no `.env.local`/Environment. `@sentry/nextjs` é **opcional**, não dependência obrigatória de `frontend/package.json`.

## Design system

Os componentes de interface do projeto usam **Tailwind CSS 3.4.17 + shadcn/ui v4 (Radix)** sobre os tokens CSS existentes (`frontend/app/globals.css` com `@tailwind` + `@layer base`; `frontend/tailwind.config.ts` espelhando `--cor-*`/`--espaco-*`/`--raio-*`/`--sombra-*`/`--z-*`; `frontend/lib/utils.ts` helper `cn`), consistente com o padrão já usado em `ThemeToggle.tsx`/`CartaoEsqueleto.tsx`; em versões anteriores, esses componentes eram CSS puro sem Tailwind.

### Datas e horas (`frontend/lib/datas.ts`)

Datas e horas devem ser formatadas pelo helper central, com locale `pt-BR` e fuso fixo `America/Sao_Paulo`;
isso evita hydration mismatch entre SSR e navegador. Novos componentes devem reutilizar os formatadores do helper, em vez de chamar `toLocale*` diretamente.

Uma string no formato civil estrito `YYYY-MM-DD` representa componentes do calendário, não um instante UTC: `2026-09-23` produz `23/09/2026` independentemente do `TZ` do processo. Entradas com hora/fuso continuam sendo instantes e são convertidas para `America/Sao_Paulo`; por exemplo, `2026-09-23T21:30:00Z` produz data `23/09/2026` e hora `18:30`.

`frontend/scripts/verificar-datas-tz.mjs` é um gate assertivo compatível com Node 18 e 20, sem flags experimentais. O workflow `ci.yml` está configurado para executá-lo em Node 20 com `TZ=UTC` e `TZ=Asia/Tokyo` antes de `tsc` e do build; a compatibilidade com Node 18 foi validada separadamente nas quatro combinações de versão/fuso.

### Tokens (`frontend/app/globals.css`)

Todo valor visual reutilizável (cor, espaçamento, tipografia, raio de borda, sombra, camada de empilhamento) é uma CSS custom property, documentada com um comentário curto de uso — nunca um valor solto espalhado pelo CSS. Categorias disponíveis hoje:

| Categoria | Exemplos | Prefixo |
|---|---|---|
| Cor | `--cor-primaria`, `--cor-erro`, `--cor-sombra` (RGB puro, usado como `rgba(var(--cor-sombra), opacidade)`) | `--cor-*` |
| Espaçamento | `--espaco-0` (0.15rem) até `--espaco-8` (4rem), incluindo meios-passos (`--espaco-1-5`, `--espaco-2-5`) | `--espaco-*` |
| Tipografia | `--fonte-tamanho-xs`..`--fonte-tamanho-xxl`, `--fonte-peso-*`, `--linha-altura-*` | `--fonte-*`, `--linha-altura-*` |
| Raio de borda | `--raio-sm`, `--raio-md`, `--raio-lg`, `--raio-completo` (pílula/círculo) | `--raio-*` |
| Sombra | `--sombra-1`..`--sombra-3` (elevação crescente) | `--sombra-*` |
| Z-index | `--z-cabecalho`, `--z-painel-flutuante`, `--z-modal`, `--z-toast`, `--z-cookies`, nomeados por papel, não por número | `--z-*` |
| Dimensão de componente | `--deslocamento-flutuante`, `--largura-max-modal`, `--tamanho-botao-icone`, etc. — medidas fixas específicas de um componente que não fazem parte da escala incremental de espaçamento | (nomes descritivos) |

**Regra a seguir sempre que criar ou alterar um componente:** nenhuma cor ou valor de espaçamento/tamanho deve ser um literal solto no CSS (ex.: `padding: 6px`, `background: rgba(0,0,0,0.5)`) — use um token existente ou, se a escala genuinamente não tiver esse degrau, crie um token novo em `globals.css`, documente o uso e referencie-o com `var(--...)`. Essa regra evita repetir o hardcode encontrado em componentes anteriores e mantém a escala visual consistente.

### Componentes reutilizáveis (`frontend/components/`)

Sete componentes genéricos, todos usando só os tokens acima, acessíveis por teclado:

| Componente | Uso típico | Comportamento de teclado/acessibilidade |
|---|---|---|
| `Badge.tsx` | Rótulo curto não interativo (ex.: selo "Premium") | N/A — não é interativo |
| `Chip.tsx` | Item selecionável/removível (ex.: filtro ativo) | `aria-pressed` para seleção; remoção como controle irmão (não aninha `<button>` dentro de `<button>`) |
| `Tooltip.tsx` | Dica contextual sobre um elemento | Aparece em hover **e** foco (não só mouse); `Escape` fecha |
| `Dropdown.tsx` | Menu de opções ancorado a um gatilho | `aria-haspopup`/`aria-expanded`; setas navegam; `Escape` fecha e devolve o foco ao gatilho; suporta item `disabled` e estado `carregando` |
| `Modal.tsx` | Diálogo modal | `Escape` ou clique fora fecham; foco fica preso dentro enquanto aberto (`Tab`/`Shift+Tab`); foco retorna ao elemento que abriu o modal ao fechar; `carregando` desabilita o fechamento |
| `Tabs.tsx` | Navegação em abas | Padrão WAI-ARIA tabs, roving tabindex (setas, Home, End); suporta aba `disabled` |
| `Accordion.tsx` | Conteúdo expansível em seções | Cabeçalho é um `<button aria-expanded>` nativo; suporta item `disabled` e modo `permitirMultiplos` |

Exemplo mínimo de uso:

```tsx
import Modal from "@/components/Modal";
import Tabs from "@/components/Tabs";

<Modal aberto={aberto} aoFechar={() => setAberto(false)} titulo="Detalhes">
  <Tabs
    abas={[
      { chave: "resumo", rotulo: "Resumo", conteudo: <p>...</p> },
      { chave: "fontes", rotulo: "Fontes", conteudo: <p>...</p> },
    ]}
  />
</Modal>
```

## Como pedir uma tarefa de desenvolvimento

Descreva o que precisa ser feito referenciando, quando possível, a seção do BRD ou uma spec em `agentic-framework/specs/`, e invoque a skill `agentic-run`. Veja `agentic-framework/prompts/request-exemplos.md` para exemplos de pedidos bem formados.

A stack técnica está decidida em `ARCHITECTURE.md` (Python/Django + React/Next.js, PostgreSQL, LLM de terceiros para resumo/curadoria, gateway de pagamento abstrato) e o primeiro recorte de requisitos (MVP + Assinatura Premium) está em `agentic-framework/specs/`. O primeiro módulo já implementado é o backend de `identidade/` (cadastro, login, login social com Google e onboarding) — ver "Como rodar o backend" acima. As specs abaixo cobrem o restante do que ainda falta construir.

### Specs prontas para virar execução (`agentic-run`)

| Spec | Epic |
|---|---|
| `agentic-framework/specs/cadastro-autenticacao-onboarding.md` | Cadastro, login, onboarding |
| `agentic-framework/specs/ingestao-curadoria-noticias.md` | Ingestão, deduplicação, classificação, agrupamento de notícias |
| `agentic-framework/specs/feed-consumo-noticias.md` | Feed, busca, categorias, página de acontecimento |
| `agentic-framework/specs/gating-free-premium.md` | Matriz de recursos e limites Free x Premium, parametrizável |
| `agentic-framework/specs/assinatura-premium.md` | Planos, pagamento, ciclo de vida da assinatura |

Cada spec lista suas próprias "Questões em aberto" — várias dependem de decisões humanas (provedor de pagamento, provedor de LLM, lista de fontes de notícia) antes da primeira execução real do módulo correspondente. Ver `ARCHITECTURE.md` seção 8 para o resumo consolidado.
