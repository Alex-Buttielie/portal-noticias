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

## Inicialização rápida (Windows/PowerShell)

```
.\scripts\init-local.ps1
```

Cria o venv do backend, instala as dependências (Python e Node), gera `backend/.env` e `frontend/.env.local` a partir dos `.example` (com uma `DJANGO_SECRET_KEY` gerada automaticamente e SQLite como banco, para não depender de um PostgreSQL local), roda as migrações e sobe os dois servidores de desenvolvimento em janelas separadas. É idempotente — pode rodar de novo quando quiser sem duplicar trabalho. Use `-SkipStart` para só preparar o ambiente sem subir os servidores, `-DbEngine postgresql` se já tiver um Postgres configurado, ou `-CreateSuperuser` para criar o superusuário do admin na mesma passada. Detalhes de cada passo (e o que fazer manualmente) abaixo.

## Como rodar o backend

Requer Python 3.13. O projeto usa Django + Django REST Framework e, por padrão, PostgreSQL.

1. Crie e ative um ambiente virtual dentro de `backend/`:

   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   # source .venv/bin/activate   # Linux/Mac
   ```

2. Instale as dependências:

   ```
   pip install -r requirements.txt
   ```

   Para reproduzir exatamente o ambiente já validado (incluindo dependências transitivas fixadas), use `pip install -r requirements-lock.txt` em vez disso.

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

5. Para rodar os testes automatizados:

   ```
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

Detalhes de payload de cada endpoint podem ser consultados diretamente no código em `backend/identidade/serializers.py` e `backend/identidade/views.py`, ou explorados de forma interativa na browsable API do Django REST Framework (acessando as URLs acima pelo navegador com o servidor rodando).

## Como popular o feed com notícias reais (ingestão)

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
5. Em produção (ou se quiser automatizar localmente), a mesma lógica roda periodicamente via Celery Beat (`CELERY_BEAT_SCHEDULE` em `config/settings.py`, intervalo em `CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS`) — exige um Redis local rodando (`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` em `.env`):

   ```
   cd backend
   .\.venv\Scripts\celery.exe -A config worker -l info
   .\.venv\Scripts\celery.exe -A config beat -l info
   ```

   (em duas janelas separadas; não é necessário para só validar funcionalidades manualmente com o comando `ingerir_noticias` acima.)

### Reduzindo custo/número de chamadas ao provedor de LLM

Por padrão, o pipeline resume os itens novos de uma execução em **lotes** de `CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE` (padrão 10) — uma única chamada HTTP cobre até 10 notícias independentes, em vez de uma chamada por notícia. Cada notícia continua recebendo um resumo gerado exclusivamente a partir do seu próprio conteúdo (nenhum resumo é compartilhado/combinado entre notícias diferentes — a mesma garantia contra atribuição incorreta de conteúdo de antes, só que aplicada a N itens por chamada). Dois parâmetros em `backend/.env` controlam isso:

- `CATALOGO_NOTICIAS_LLM_TAMANHO_LOTE`: quantas notícias por chamada. Um valor maior reduz ainda mais o número de chamadas, mas se a chamada inteira falhar (rede, resposta malformada), todas as notícias daquele lote caem juntas na fila de revisão humana em vez de só uma.
- `CATALOGO_NOTICIAS_LLM_MAX_TOKENS_POR_ITEM`: teto de tokens de resposta por notícia (padrão 220), multiplicado pelo tamanho do lote — evita pagar por respostas mais longas que o necessário para um resumo curto.

Depois de uma execução, o campo "Chamadas summarization provider" de cada `RegistroExecucaoIngestao` (`http://localhost:8000/admin/catalogo_noticias/registroexecucaoingestao/`) mostra quantas chamadas HTTP reais foram feitas — é o número que comprova a redução (ex.: 30 notícias novas viram 3 chamadas com o lote padrão de 10, em vez de 30).

## Como rodar o frontend

Requer Node.js 18+. O projeto usa Next.js (App Router) + TypeScript, sem framework de CSS adicional.

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

Não construído ainda: login social (Google) na interface, e qualquer tela para os módulos do BRD ainda sem backend (Comunidade, Credenciamento, Radar, B2B, Newsletter, Landing Page).

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
