# P1-01b — caminho de escrita do Admin passa pela politica de limites

Defeito fechado, evidencia medida antes/depois, e a varredura dos demais
`ModelAdmin` que ficaram de fora (item 6 do enunciado, reportado e nao
corrigido por decisao de escopo).

Base das medicoes: `int-v2` = `411f30d` (merge do P0-10). Ambiente: Django
5.2.17, **PostgreSQL 16.15 real** (`postgres:16-alpine`) — SQLite ignora
`varchar(N)` e nao reproduz o defeito.

---

## 1. A prova antes/depois

Metodo: POST **real** de changeform pelo admin (login + sessao + reverse do
admin), `follow=False`, e releitura do objeto no banco. Script completo em
`p101b-prova-admin-script.py`.

### ANTES (`docs/evidencias/p101b-prova-antes.txt`)

```
item </script> — HTTP                                | 302
item </script> — persistiu byte-identico             | True
item </script> — tem '</script>' no banco            | True
item </script> — titulo lido do banco                | "Prefeitura anuncia obra </script><script>alert('XSS-ARMADO')</script>"
cluster </script> — HTTP                             | 302
cluster </script> — persistiu byte-identico          | True
cluster </script> — titulo lido do banco             | 'Vazamento emacapetuba </script><img src=x onerror=alert(1)>'
```

### DEPOIS (`docs/evidencias/p101b-prova-depois.txt`)

```
item </script> — HTTP                                | 302
item </script> — persistiu byte-identico             | False
item </script> — tem '</script>' no banco            | False
item </script> — titulo lido do banco                | 'Prefeitura anuncia obra'
cluster </script> — HTTP                             | 302
cluster </script> — persistiu byte-identico          | False
cluster </script> — titulo lido do banco             | 'Vazamento emacapetuba'
```

O POST continua sendo aceito (302) — o titulo nao e recusado, e saneado — e o
operador recebe o aviso na propria tela:

```
Admin: politica de limites ajustou NewsItem(pk=None): 'titulo' foi ajustado
pela politica de limites do catalogo (69 -> 23 caracteres; HTML removido e/ou
corte em 300). Revise o valor exibido.
```

O conteudo editorial sobrevive; o que some e a marcação.

### O que a medicao tambem mostrou (e o enunciado nao previa)

Estes dois casos **ja** eram barrados antes da mudanca, pelo `ModelForm` do
proprio Django (que valida `max_length` do `CharField` do modelo). Medido nas
duas execucoes, **identico** antes e depois:

```
titulo longo (420 chars, varchar 300) — HTTP         | 200
titulo longo — erros do form                         | ['Certifique-se de que o valor tenha no máximo 300 caracteres (ele possui 420).']
url longa (1205 chars, varchar 1000) — HTTP          | 200
url longa — a URL inteira foi preservada             | False
url longa — erros do form                            | ['Certifique-se de que o valor tenha no máximo 1000 caracteres (ele possui 1205).  URL da fonte original e obrigatoria (rastreabilidade — BRD secao 18).']
```

Ou seja: **o vazao real do defeito era o HTML cru (`</script>`), nao o
excedente de tamanho.** A truncagem com aviso e a recusa com mensagem
continuam implementadas e testadas, mas como **defesa em profundidade** para
o chamador que nao passa pelo formulario do Admin — e nao como correcao de um
defeito observavel na tela. Isso esta dito no codigo e no relatorio para que
ninguem leia "trunca com aviso" como se fosse o buraco fechado.

---

## 2. Inventario dos caminhos de escrita de `NewsItem` / `NewsCluster`

Todos medidos no codigo desta base. "Passa pela politica" = chama
`services.limites.aplicar_limites_*` antes do INSERT/UPDATE.

| # | Caminho de escrita | `arquivo:linha` | Passa pela politica? |
|---|---|---|---|
| 1 | Ingestao: construtor do item | `backend/catalogo_noticias/services/ingestao.py:632` (`_construir_news_item`) | Sim (P1-01) |
| 2 | Ingestao: construtor do cluster | `backend/catalogo_noticias/services/ingestao.py:648` (`_criar_cluster`) | Sim (P1-01) |
| 3 | Ingestao: ultima porta antes do INSERT em lote | `backend/catalogo_noticias/services/ingestao.py:430` (`_persistir_news_items_em_lote` -> `limitar_textos`) | Sim (P1-01) |
| 4 | **Admin: `NewsItemAdmin.save_model`** | `backend/catalogo_noticias/admin.py:97` (chama `LimitesAdminMixin.save_model` via `super()`) | **Era nao. Agora sim.** |
| 5 | **Admin: `NewsClusterAdmin.save_model`** | `backend/catalogo_noticias/admin.py:39` (mesmo mixin) | **Era nao. Agora sim.** |
| 6 | Admin: `NewsItemInline` (dentro do cluster) | `backend/catalogo_noticias/admin.py:29` | Nao se aplica — inline **totalmente somente leitura** (`readonly_fields = fields`, `extra = 0`, `can_delete = False`); medido na varredura |
| 7 | Admin: acoes em lote `marcar_como_aprovado` / `marcar_como_rejeitado` | `backend/catalogo_noticias/admin.py:118` e `:132` | Nao se aplica — `queryset.update(status_revisao=...)`, nao tocam campo de texto |
| 8 | API do painel: `FilaDecisaoView` -> `decidir_fila` | `backend/painel_admin/services.py:22` e `:26` | Nao se aplica — so `status_revisao` |
| 9 | API do painel: serializadores | `backend/painel_admin/serializers.py:24` (`FilaItemSerializer`), `:114` (`FilaDecisaoSerializer`), `:129` (`DestaqueEditorialAdminSerializer`) | Nao se aplica — `titulo` e `cluster_titulo` sao **so leitura** (`read_only=True` / sem `ModelSerializer` de escrita); nenhum serializer de `NewsItem`/`NewsCluster` aceita `titulo` |
| 10 | Central de inteligencia (metricas) | `backend/metricas/services_inteligencia.py:157`-`:170` | Nao se aplica — so leitura |
| 11 | Tasks de ingestao / newsletter / b2b / radar / feed | `backend/catalogo_noticias/tasks.py`, `backend/newsletter/tasks.py`, `backend/b2b/services.py:82`, `backend/radar/services.py:25` | Nao se aplica — leem `NewsItem` |
| 12 | Management commands | `backend/catalogo_noticias/management/commands/ingerir_noticias.py`, `descobrir_feeds.py`, `sincronizar_fontes_padrao.py` | Nao se aplica — `descobrir_feeds`/`sincronizar_fontes_padrao` escrevem `FonteRobo`, nao `NewsItem`; `ingerir_noticias` so chama `executar_ingestao` (caminho 1-3) |
| 13 | `bulk_create` / `update` / `delete` em `ingestao.py` | `backend/catalogo_noticias/services/ingestao.py:453`, `:795`, `:819`, `:800`, `:903` | Sim para os que passam por 1-3; os demais mexem so em `cluster_id` / `status_revisao` |

**Nenhum outro caminho de escrita de texto em `NewsItem`/`NewsCluster` existe.**
O enumero de 3 era o unico que criava os objetos, e ele ja passava pela
politica; o unico buraco era o Admin (4 e 5).

---

## 3. A politica do Admin (decisao, e onde esta documentada)

Decidida e documentada em **duas** camadas, para nao haver duas politicas:

* **`backend/catalogo_noticias/limites_admin.py`, docstring do modulo** —
  o texto longo que explica *por que* `save_model` e nao `form.save()`, *por
  que* truncar e *por que* `url_fonte_original` nao pode ser truncado, e a
  exigencia de idempotencia.
* **`backend/catalogo_noticias/admin.py:67` e `:39`** — o comentario de cada
  `ModelAdmin` aponta para a mixin e diz o que mudou.

As tres regras, que vem de `services/limites.py` (nao sao novas):

| Classe de campo | No Admin | Por que |
|---|---|---|
| `TRUNCAR` (`titulo`, `resumo_proprio`, `conteudo_*`, `categoria`, `autor`, `pais`/`estado`/`cidade`, `status_revisao`, `nome_fonte`, `titulo_acontecimento`, `categoria_dominante`) | limpa HTML + trunca com elipse + **`message_user` de aviso** dizendo quais campos mudaram | O guarda do P1-01 ja aceitou truncar no Admin "porque o operador esta vendo e corrigindo" — mas so ajuda se ele **saber**. Erro de formulario foi descartado de proposito: impediria aprovar/rejeitar a noticia, trocando risco de exibicao por risco operacional (fila de revisao travada). |
| `DESCARTAR_CAMPO` (`imagem_url`) | zera + avisa | URL de imagem cortada aponta para recurso inexistente. |
| `RECUSAR_ITEM` (`url_fonte_original`) | **recusa com mensagem clara**, checada no `ModelForm` | Truncar a URL fabricaria outra materia (BRD secao 18). A checagem fica no formulario porque e ele que vira **erro de campo**; um `save_model` levantando excecao devolveria HTTP 500 — recusa sem mensagem, pior que o defeito. |

Um unico comportamento por classe de campo, e as classes vem da politica
existente — nao ha segunda tabela de campos no Admin (o mapa
`APLICAR_LIMITES_POR_MODEL` e derivado dela, e um teste trava isso).

---

## 4. Testes (18, em `backend/catalogo_noticias/tests/test_p1_01b_admin_limites.py`)

| Teste | O que prova |
|---|---|
| `test_admin_nao_persiste_script_no_titulo_do_item` | **o defeito:** `</script>` no titulo via POST real nao persiste byte-identico; o texto editorial sobrevive |
| `test_admin_avisa_que_ajustou_o_titulo` | o saneamento/corte e **avisado**, nao silencioso |
| `test_admin_nao_persiste_script_no_titulo_do_cluster` | o mesmo para `NewsCluster.titulo_acontecimento` (que estava igualmente aberto) |
| `test_save_model_trunca_titulo_acima_do_limite_e_avisa` | `save_model` direto com titulo de 420 chars: grava dentro do teto **e** avisa |
| `test_aplicar_limites_no_admin_corta_com_elipse` | o corte preserva o texto util e marca a elipse |
| `test_admin_recusa_url_acima_do_limite_com_mensagem` | E2E: URL de 1205 chars -> HTTP 200, nada persistido, erro **no campo** citando o teto |
| `test_form_do_admin_recusa_url_acima_do_limite_mesmo_sem_max_length_do_campo` | a checagem do mixin **existe e funciona** mesmo quando o campo do formulario e mais permissivo que a politica (form customizado futuro) — nao e linha morta sob o `max_length` |
| `test_save_model_recusa_url_acima_do_limite_com_erro_explicito` | a ultima linha de defesa: `save_model` **levanta** em identificador fora do limite, com o teto no texto |
| `test_editar_so_outro_campo_nao_corrompe_o_titulo` | **edicao legitima:** mexer so em `status_revisao` de item cujo titulo a ingestao ja truncou nao corrompe o titulo, nao encolhe, nao da erro e **nao avisa** |
| `test_truncamento_e_idempotente_ao_salvar_duas_vezes` | reenviar o valor CRU duas vezes da o mesmo resultado; reenviar o valor ja saneado nao muda nem avisa |
| `test_aplicar_limites_no_admin_e_idempotente` | a 2a chamada da funcao nao muda nada e nao devolve nota |
| `test_editar_so_outro_campo_do_cluster_nao_corrompe_o_titulo` | o mesmo para `NewsCluster` |
| `test_ingestao_continua_limpando_limitando_e_recusando` | **nao-regressao:** `executar_ingestao` real ainda limpa HTML, respeita o teto, recusa URL gigante, registra a falha no log **e** no `erros_por_fonte` do `RegistroExecucaoIngestao` |
| `test_ingestao_persiste_item_com_html_malicioso_sem_script` | o que a ingestao grava ja vem limpo, entao reaplicar a politica do Admin sobre ele nao gera aviso |
| `test_mixin_ignora_models_fora_da_politica` | o mixin e opt-in: aplicado por engano a outro model, devolve lista vazia em vez de explodir |
| `test_mapa_do_admin_cobre_exatamente_os_models_da_politica` | cross-check do mapa contra os models que `services/limites.py` declara |
| `test_as_duas_admin_do_catalogo_herdam_o_mixin` | os dois `ModelAdmin` estao com a mixin (regressao contra remocao silenciosa) |
| `test_inline_de_newsitem_e_totalmente_somente_leitura` | trava a premissa de que o inline nao e caminho de escrita |

Todos os limites sao lidos de `Model._meta.get_field(campo).max_length` — a
mesma fonte de verdade do codigo de producao e dos testes do P1-01.

### Uma correcao de ambiente que os testes expoem

`config.settings.STORAGES` usa `CompressedManifestStaticFilesStorage`, que le
o `staticfiles.json` produzido por `collectstatic` — arquivo que a suite nao
gera. Qualquer teste que espere a tela de mudanca **reexibida** (HTTP 200)
tomava `ValueError: Missing staticfiles manifest entry for 'admin/css/base.css'`
e virava 500. Isso nao afetava os testes de Admin que existiam porque eles
esperam 302 (redirect, sem template). O fixture `_armazena_staticfiles_sem_manifest`
troca **so** o armazenamento de static, no escopo do arquivo de teste.
`STORAGES["default"]` (media de upload) fica como esta, e nenhuma mudanca de
configuracao de producao foi feita.

---

## 5. Suite e cobertura

| | `int-v2` = `411f30d` (base) | `p1-01b-admin-limits` (apos) |
|---|---|---|
| testes | 770 passed | **788 passed** (+18, todos deste item) |
| cobertura | 89.54% | **89.89%** |
| exit | 0 | 0 |

Linhas finais (`pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80`):

```
base  (docs/evidencias/p101b-suite-baseline.txt)
Required test coverage of 80% reached. Total coverage: 89.54%
770 passed, 248 warnings in 279.89s (0:04:39)
EXIT=0

depois (docs/evidencias/p101b-suite-depois.txt)
Required test coverage of 80% reached. Total coverage: 89.89%
788 passed, 289 warnings in 189.65s (0:03:09)
EXIT=0
```

A referencia "536 passed / 89,39%" do enunciado foi **medida e confirmada** em
`int-v2` = `29da732`, **antes** do merge do P0-10 (que somou 234 testes):

```
Required test coverage of 80% reached. Total coverage: 89.39%
536 passed, 216 warnings in 126.12s (0:02:06)
EXIT=0
```

(medido com a suite da arvore de `int-v2` = `29da732`; o arquivo nao foi
retido, porque a unica medicao de baseline que importa para este item e a da
base **atual**, reproduzida acima e retida em `p101b-suite-baseline.txt`. Os
dois numeros sao de bases diferentes e nenhum foi assumido.)

---

## 6. `manage.py check` / `check --deploy`

```
$ manage.py check
System check identified no issues (0 silenced).
```

```
$ manage.py check --deploy
W004 SECURE_HSTS_SECONDS nao definido
W008 SECURE_SSL_REDIRECT nao definido
W012 SESSION_COOKIE_SECURE nao True
W016 CSRF_COOKIE_SECURE nao True
W018 DEBUG esta True
System check identified 5 issues (0 silenced).
```

Comparado com a **mesma** execucao na arvore de `int-v2`: os mesmos 5 IDs,
o mesmo total, nenhum novo (`p101b-check-deploy-baseline.txt` vs
`p101b-check-deploy-depois.txt`). Os 5 sao de ambiente local de teste
(`DJANGO_DEBUG=true` no script de env, e as 4 opcoes de transporte/HTTPS que
a producao define por variavel) — nenhum vem deste item.

---

## 7. Varredura dos OUTROS models (item 6 — reportado, NAO corrigido)

Varredura de TODO `admin.site._registry` + todos os inlines, contando campo
**realmente editavel** (`disabled=False` no form do admin, e nao apenas
"ausente de `readonly_fields`"): `p101b-varredura-admin-depois.txt`.

Acharam-se **26** `ModelAdmin` com campo de texto editavel. Duas agora passam
pela politica (`NewsItem`, `NewsCluster`). As outras 24, por ordem de
interesse, com o risco real de cada uma:

### Risco 1 — valor de TEXTO renderizado em JSON-LD / HTML publico (mesmo padrao do achado deste item)

| Model | Admin | `arquivo:linha` | Campos |
|---|---|---|---|
| `comunidade.Publicacao` | `PublicacaoAdmin` | `backend/comunidade/admin.py:7` | `titulo` (300), `conteudo` (TextField), `categoria` (100) |
| `moderacao.PaginaEditorial` | `PaginaEditorialAdmin` | `backend/moderacao/admin.py:48` | `titulo` (200), `conteudo` (TextField) |
| `moderacao.Denuncia` | `DenunciaAdmin` | `backend/moderacao/admin.py:14` | `motivo` (20), `detalhe` (TextField), `resolucao_motivo` (TextField) |
| `comunidade.Comentario` | `ComentarioAdmin` | `backend/comunidade/admin.py:14` | `conteudo` (TextField) |
| `moderacao.RecursoModeracao` | `RecursoModeracaoAdmin` | `backend/moderacao/admin.py:26` | `texto` (TextField) |
| `moderacao.AcaoModeracao` | `AcaoModeracaoAdmin` | `backend/moderacao/admin.py:20` | `motivo` (TextField) |
| `feed.DestaqueEditorial` | `DestaqueEditorialAdmin` | `backend/feed/admin.py:22` | `motivo` (300) |

Observacao util: `moderacao.PaginaEditorial.conteudo` **ja** e sanitizado, mas
pelo serializer de API (`backend/moderacao/serializers.py:86` e `:109`, com
`config.sanitizar_html`) e **nao** pelo `PaginaEditorialAdmin` — ou seja, o
caminho do Admin e um contorno daquele. Nao corrigido aqui.

### Risco 2 — `TextField` sem teto no banco, sem limite de aplicacao

`credenciamento.SolicitacaoCredenciamento` (`mini_bio`, `dados_profissionais`,
`motivo_decisao`), `credenciamento.PerfilJornalista` (`motivo_suspensao`,
`mini_bio`, `dados_profissionais`), `socialaccount.SocialToken`
(`token`, `token_secret`).

`TextField` no PostgreSQL vira `text` (limite ~1 GB), entao nao ha `DataError`
a guardar — mas nao ha teto de aplicacao nenhum. Requer **politica nova por
modelo** (sao conteudo do usuario / segredo de terceiro, nao conteudo de fonte
externa), o que e exatamente o que o enunciado mandou nao absorver neste item.

### Risco 3 — identificadores e URLs editaveis sem politica

`catalogo_noticias.FonteRobo` (`nome` 150, `url` 1000, `categoria_padrao` 100,
`estado_padrao` 2), `b2b.Organizacao` (`nome` 200), `b2b.MembroOrganizacao`
(papel, 20), `b2b.CriterioMonitoramento` (`tipo` 20, `valor` 200 — **inline
editavel**), `assinatura.Plan` (`nome` 100), `landing.InscricaoListaEspera`
(`nome` 150, `email` 254, `localidade` 150, `canal_preferido` 20),
`identidade.User` (`email` 254, `nome` 150), `allauth.EmailAddress`/
`SocialAccount`/`SocialApp` (terceiros), `django.contrib.Site`/`Group`
(terceiros), `moderacao.ReputacaoEventoLog` (`motivo` 300).

`FonteRobo.url` e o caso mais serio da lista: e a URL de feed consumida pelo
pipeline de ingestao, e um `URLField` unique de 1000 chars.

### O que NAO foi feito, e por que

Nenhum desses foi corrigido: **nao ha politica de limites para eles.** A
politica do P1-01 le os limites do MODELO e declara tetos de aplicacao so para
os `TextField` do catalogo de noticias; estender a `Publicacao.titulo`,
`PaginaEditorial.conteudo` ou `FonteRobo.url` significa **inventar politica
nova** (quais campos truncam, quais recusam, quais tem teto) para 7 apps —
justamente o que o enunciado mandou reportar em vez de absorver. E a correcao
de cada um depende de onde o valor e renderizado (o `Publicacao` aparece em
feed, perfil e busca; o `PaginaEditorial` em pagina publica), o que exige a
mesma verificacao de renderizacao que o P0-10 esta fazendo no frontend.

O que fica pronto para quem for pegar: `LimitesAdminMixin` e generico na
 forma — basta uma funcao `aplicar(modelo)->notes` por model e o `ModelAdmin`
correto. O que falta nao e o mecanismo, e a politica de cada modelo.

---

## 8. Portoes do repositorio e gates

* `.github/` — **intocado.** `git diff --name-only int-v2` nao contem nada
  de `.github/`.
* `frontend/` — **intocado**, apesar de o P0-10 ter entrado em `int-v2`
  durante o trabalho deste item (rebases manuales, ver secao 9).
* `migrations/` — **intocadas.** Nenhuma migration nova: a correcao e de
  aplicacao da politica, nao de esquema.
* `infra/`, `.env*`, `run-state.json`, lockfile, `.gitignore` — intocados.
* Gate do P0-1:
  `sha256sum scripts/release/verificar-proveniencia.sh` =
  `133408e55076f4c71fa439ee2588d94b55f540e4d29da3296d0858bd592a9541` (igual
  ao do enunciado).
* Regra `segredo-chave-valor-literal`: as expressoes `CHAVE_GENERICA` +
  `valor_plausivel` do proprio gate aplicadas aos 4 arquivos deste item
  → **0 achado plausivel**, 1 candidato descartado pelo filtro de placeholder
  (a senha de teste do superuser, que contem `senha`).
* Nenhum `__pycache__`, `.pytest_cache`, `.coverage` ou `db.sqlite3`
  versionado (todos ja ignorados por `backend/.gitignore`, que **nao** foi
  editado).

---

## 9. Uma coisa que precisa constar: `int-v2` andou duas vezes

O worktree foi criado em `int-v2` = `4a1b64a`, como o enunciado pedia. Durante
o trabalho, `int-v2` recebeu **dois** commits de outros agentes:

1. `29da732 fix(tests): declara placeholder na chave de Resend do teste de boot
   de e-mail` — corrigia **exatamente** um achado da regra
   `segredo-chave-valor-literal` que o enunciado me avisava para nao
   introduzir. Ele **existia na base** `4a1b64a` que eu tinha, em
   `backend/config/tests/test_settings_producao.py:714`
   (`RESEND_API_KEY="re_0000000000000000000000000000000"`): 32 caracteres, 4
   classes, sem marcador de placeholder. Nao era meu, e nao era eu quem podia
   consertao.
2. `411f30d merge(P0-10)` — o hardening de seguranca, incluindo o escape de
   JSON-LD no frontend.

A branch foi rebaseada duas vezes e esta em `dfe37f4`, sobre `411f30d`. O
diff contra `int-v2` atual tem **exatamente 4 arquivos, todos de
`backend/catalogo_noticias/`**. Nada de `.github/`, `frontend/` ou
migrations.

Duas consequencias honestas:

* O par de medicoes antes/depois foi tirado com a arvore de `int-v2` = `411f30d`
  nos **dois** lados, entao e diretamente comparavel. (A primeira medicao do
  "antes" foi em `4a1b64a` e deu o mesmo resultado para o defeito — o P0-10 nao
  tocou `catalogo_noticias/admin.py`.)
* As duas referencias de suite do enunciado sao de bases diferentes:
  "536 passed / 89,39%" = `int-v2` **antes** do P0-10; sobre o `int-v2` atual
  a base e 770. Os dois numeros foram medidos, nenhum foi assumido.

---

## 10. Complementaridade com o P0-10 (nao substituto)

O P0-10 fecha o lado da **renderizacao** (escapa JSON-LD, sanitiza HTML
editorial). Este item fecha o lado da **escrita**. Os dois sao necessarios:

* Sem o P0-10, este item deixa de armadilha obvio, mas o titulo sujo continua
  no banco e sai em toda renderizacao que nao passe pelo escape de JSON-LD.
* Sem este item, o P0-10 deixa o banco sujo, e qualquer consumidor futuro
  (export, e-mail, outro app, um `JsonLd.tsx` esquecido) reabre o vetor.

Verificado que **nao ha sobreposicao**: `int-v2`..`411f30d` nao toca
`backend/catalogo_noticias/admin.py`, e `config.sanitizar_html` (P0-10) so e
aplicado em `moderacao/serializers.py`, com semantica diferente — ele
**escapa** (`&lt;`) reconstruindo o documento, enquanto a politica de limites
**remove** a marca��ao e reduz a texto puro, porque o `NewsItem` guarda texto
limpo por contrato (BRD secao 18) e nao HTML.
