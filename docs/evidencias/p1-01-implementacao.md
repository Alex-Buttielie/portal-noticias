# P1-01 — Ingestão: limites de campos e isolamento de falha

Item de backlog **P1-01** (workstream **WS-08**, gate **GP-5**).

Critério de saída atendido:

> "Valores grandes não causam `DataError`; erro não aborta todos os grupos"

## 1. Diagnóstico (na base `06745d1`)

Comando de ingestão: `backend/catalogo_noticias/management/commands/ingerir_noticias.py`
(atalho manual) → `services/ingestao.py::executar_ingestao`. Em produção a mesma
função é chamada pela task `catalogo_noticias/tasks.py`.

Pontos de escrita do `NewsItem` (todos em `services/ingestao.py`, antes desta
correção, **sem limite algum**):

| local | o que escrevia |
|---|---|
| `_persistir_news_items_em_lote:413` | `NewsItem.objects.bulk_create(...)` — o `DataError` nascia aqui |
| `_persistir_grupo:486` | `NewsCluster.objects.create(titulo_acontecimento=grupo[0].titulo, ...)` |
| `_persistir_grupo:495,518-535` | construção do `NewsItem` (`titulo`, `categoria`, `imagem_url`, `pais`, `estado`, …) |
| `_persistir_grupo_mesclado:623,661-674` | **cópia duplicada** da construção acima |
| `executar_ingestao:1005` | chamada sem proteção nenhuma de `_persistir_grupo` |

Origem dos valores: `providers/news_source.py:452-458` — `titulo`, `url_fonte_original`,
`categoria` e `imagem_url` saíam do feedparser com `.strip()` e **sem teto**. A
categoria também vem do LLM (`resultado.categoria`), que também não tinha teto.

### `max_length` reais (lidos de `_meta` e conferidos no DDL do PostgreSQL)

```
NewsItem.titulo              varchar(300)     NewsItem.pais          varchar(100)
NewsItem.url_fonte_original  varchar(1000)    NewsItem.estado        varchar(100)
NewsItem.nome_fonte          varchar(150)     NewsItem.cidade        varchar(150)
NewsItem.categoria           varchar(100)     NewsItem.imagem_url    varchar(1000)
NewsItem.autor               varchar(200)     NewsItem.status_revisao varchar(20)
NewsItem.resumo_proprio      text (sem limite)
NewsItem.conteudo_bruto      text (sem limite)
NewsItem.conteudo_completo   text (sem limite)

NewsCluster.titulo_acontecimento varchar(300)  NewsCluster.categoria_dominante varchar(100)
```

### Onde um valor grande estourava — prova medida

`docs/evidencias/p1-01-defeito-antes.txt`, reproduzido em PostgreSQL real
(`psycopg2.errors.StringDataRightTruncation`):

```
psycopg2.errors.StringDataRightTruncation: value too long for type character varying(300)
django.db.utils.DataError: value too long for type character varying(300)
  services/ingestao.py:1005 executar_ingestao -> _persistir_grupo
  services/ingestao.py:538  _persistir_grupo   -> _persistir_news_items_em_lote
  services/ingestao.py:413  _persistir_news_items_em_lote -> bulk_create
```

Um único título de 5000 caracteres derrubou a rodada **inteira**: a fonte
seguinte no lote não chegou a ser processada. O mesmo para `categoria`
(varchar 100), `imagem_url` (1000), `nome_fonte`/`pais`/`estado` (150/100/100) e
`NewsCluster.titulo_acontecimento` (300).

Prova por suíte: `docs/evidencias/p1-01-pytest-antes.txt` — **21 failed, 4 passed**
antes da correção; `docs/evidencias/p1-01-pytest-depois.txt` — **32 passed** depois.
Os 4 que já passavam são os de "exatamente no limite", e é por isso que eles
servem de contraprova de off-by-one: passa na base (nada é truncado) e continua
passando depois (o limite está no ponto certo).

### Segundo defeito encontrado no mesmo caminho: HTML cru no banco

`docs/evidencias/` registra a reprodução. `NewsItem.titulo` e
`NewsItem.conteudo_bruto` recebiam o RSS **cru**: `<script>alert('xss')</script>`
ficava literalmente gravado. `titulo` chega ao frontend em
`<script type="application/ld+json">` via `JSON.stringify` (`frontend/app/noticia/[id]/page.tsx:33`),
que **não** escapa `<` nem `/` — XSS armazenado.

### Terceiro: pico de memória

`extrair_conteudo_completo` truncava **depois** de limpar o HTML: 3,2 MB de HTML
viravam 3,2 MB de texto e só então cortados para 8.000 caracteres. Medido antes
da correção: `texto depois de limpar_html_para_texto: 3199999 chars`.

## 2. O que mudou

| arquivo | mudança |
|---|---|
| `catalogo_noticias/limites_texto.py` (novo) | utilitários de texto **puros** (sem models): `limpar_html_para_texto`, `truncar`, `cortar_em_limite_seguro`. Compartilhados por provider e serviço — duas cópias divergiriam. |
| `catalogo_noticias/services/limites.py` (novo) | limites **lidos de `_meta`** (fonte de verdade = DDL), política por campo, tetos de `TextField` com justificativa, e o coletor de placar de falhas. |
| `services/ingestao.py` | `_construir_news_item` / `_construir_news_cluster` (construtor único, substitui as duas cópias); isolamento por item, por grupo e na sumarização; backstop de `DataError` linha a linha; limite no `update_fields`; placar de sucesso/falha; guarda de validator. |
| `providers/news_source.py` | tetos de memória por campo, corte do HTML **antes** da limpeza, saneamento de HTML/entidades, descarte de URL e imagem inservíveis. |

### Política de limite por campo — truncar não serve para tudo

* **`truncar`** (texto de exibição): `titulo`, `resumo_proprio`, `conteudo_bruto`,
  `conteudo_completo`, `categoria`, `nome_fonte`, `pais`/`estado`/`cidade`,
  `status_revisao`, `titulo_acontecimento`, `categoria_dominante`.
* **`descartar_campo`**: `imagem_url` — URL cortada aponta para recurso inexistente,
  que é pior que não ter imagem. Vira `""` e o item entra.
* **`recusar_item`**: `url_fonte_original` — truncar fabricaria **outra** matéria.
  O item é recusado com motivo explícito e vira entrada no placar de falhas.

### Tetos de aplicação (os únicos números que não vêm do modelo)

| campo | teto | justificativa |
|---|---|---|
| `resumo_proprio` | 4.000 | `llm_max_tokens_por_item` = 220 (~1.000 chars) → ~4× de folga |
| `conteudo_bruto` | 20.000 | cópia de auditoria (BRD §18: nunca exibida); ~20 KB/item × janela de dedup de 300 = dezenas de MB, não GB |
| `conteudo_completo` | 8.000 | **mesma constante** do provider, importada — não há dois tetos |

### Decisões que merecem destaque

1. **A construção do `NewsItem` estava duplicada** em `_persistir_grupo` e
   `_persistir_grupo_mesclado`. Um limite esquecido numa das cópias só apareceria
   no caminho de mesclagem. Agora há um construtor só.
2. **O limite é aplicado no serviço, não na view nem só no provider** — e
   reaplicado em `_persistir_news_items_em_lote`, a última porta antes do
   `INSERT`, para que um chamador novo herde a garantia sem saber que
   `services/limites` existe (`test_persistencia_limita_item_montado_fora_do_construtor`).
3. **`DataError` tem dois tratamentos diferentes de `IntegrityError`.** Conflito
   de unicidade = corrida entre execuções, resolvido com `ignore_conflicts`.
   `DataError` = valor grande; o `INSERT` em lote é tudo-ou-nada, então há
   fallback **linha a linha**, cada uma no seu savepoint. Qualquer outro
   `DatabaseError` (violação de CHECK) é falha da transação, não de um item:
   é registrado e **re-lançado** para o isolamento por grupo decidir.
4. **Guarda de perda de dados preservada.** Isolar a falha de grupo não pode
   deixar o `ETag` avançar: a próxima rodada levaria um 304 e os itens perdidos
   nunca mais voltariam. As fontes cujo grupo falhou **não** confirmam validator.
5. **Item recusado por limite ≠ item em risco.** A recusa por `varchar` é
   determinística e permanente, então o validator **avança** para essa fonte
   (re-baixar o feed a cada 15 min para reencontrar o mesmo item inválido seria
   desperdício). O que não pode é erro **transitório** virar perda definitiva —
   e esse cai no caso do grupo.

## 3. Testes — 32 no arquivo novo

`backend/catalogo_noticias/tests/test_p1_01_ingestao_limites.py`.
Os limites dos testes são lidos de `_meta`, então se o `max_length` do modelo
mudar, os testes passam a medir o limite novo sem edição.

### Limite de campo

| teste | o que prova |
|---|---|
| `test_regressao_titulo_enorme_nao_derruba_a_execucao_nem_os_itens_validos` | título de 5000 chars + fonte boa depois: ambos entram (**falhava na base**) |
| `test_regressao_url_enorme_e_registrada_sem_derrubar_o_resto` | URL gigante é **recusada** (não truncada) e registrada com fonte + limite real |
| `test_regressao_categoria_enorme_do_llm_nao_derruba_a_execucao` | categoria de 500 chars vindo do **LLM** |
| `test_regressao_categoria_enorme_vinda_do_rss_nao_derruba_a_execucao` | mesma coisa pelo caminho do **RSS** (independente do LLM) |
| `test_regressao_imagem_url_enorme_e_descartada_sem_derrubar_o_item` | `imagem_url` zerada, item entra |
| `test_regressao_nome_fonte_e_localidade_enormes_sao_limitados` | `nome_fonte`/`pais`/`estado` limitados |
| `test_regressao_titulo_de_cluster_enorme_nao_derruba_a_execucao` | 2 fontes no mesmo fato com título gigante: cluster limitado **e** os 2 `NewsItem` criados |
| `test_regressao_categoria_dominante_enorme_no_cluster_nao_derruba_a_execucao` | `categoria_dominante` limitado |
| `test_campo_exatamente_no_limite_passa_intacto` | valor == `max_length` passa byte a byte (sem off-by-one) |
| `test_url_exatamente_no_limite_e_aceita` | URL de exatamente 1.000 chars aceita |
| `test_um_caractere_acima_do_limite_e_o_unico_que_muda` | com `max_length + 1`, só a elipse muda |

### Truncagem não quebra encoding nem produz HTML malformado

| teste | o que prova |
|---|---|
| `test_truncagem_nao_parte_sequencia_multiponto_de_grafema` | não corta acento combinante, ZWJ de emoji nem bandeira pela metade; round-trip UTF-8 pelo banco |
| `test_html_com_script_no_titulo_e_neutralizado_antes_de_persistir` | `<script>` do RSS não chega ao banco (**falhava na base**) |
| `test_html_com_script_no_resumo_do_llm_e_neutralizado` | idem no `resumo_proprio` |
| `test_resumo_ou_conteudo_com_tag_desbalanceada_nao_gera_html_malformado_para_render` | tag aberta e não fechada não vira markup malformado |
| `test_html_e_entidades_do_rss_viram_texto_no_provider` | `<b>` sai, `&mdash;` vira `—`, `<script>` não sobrevive |
| `test_corte_do_html_bruto_respeita_fronteira_de_tag` | corte do HTML cru cai em `>` (nada de tag pela metade) |

### Isolamento de falha

| teste | o que prova |
|---|---|
| `test_regressao_item_invalido_no_meio_de_lote_valido_nao_derruba_o_lote` | item inválido no **meio**: os válidos entram, o inválido é registrado (**falhava na base**) |
| `test_regressao_grupo_inteiro_invalido_nao_derruba_os_outros_grupos` | fonte inteira falha: as outras seguem; o item que falhou entra em `pendente`, **nunca** publicado |
| `test_erro_nao_e_engolido_registra_fonte_item_e_motivo` | `RuntimeError` inesperado → log ERROR **com traceback**, com fonte de cada item, e no registro |
| `test_placar_de_sucesso_e_falha_e_reportado_ao_final` | placar separa *candidatos* de *ingeridos*: "3 candidato(s), 2 INGIRIDO(S), 1 recusado(s)/isolado(s)" |
| `test_data_error_do_banco_nao_propaga_da_persistencia` | `DataError` real injetado no `bulk_create` não propaga e é registrado |
| `test_persistencia_limita_item_montado_fora_do_construtor` | **defesa em profundidade**: item montado direto (sem o construtor) ainda é limitado |
| `test_persistencia_recusa_item_com_url_fora_do_limite_montado_fora_do_construtor` | o mesmo, para URL: recusa o ruim, entra os bons |

### Idempotência, memória e não-drift

| teste | o que prova |
|---|---|
| `test_reprocessar_o_mesmo_lote_nao_duplica` | 2 itens rodados 2× = 2 no banco, 0 na 2ª rodada |
| `test_reprocessar_item_enorme_que_foi_limitado_nao_cria_duplicata` | idempotência também no caminho já truncado |
| `test_conteudo_bruto_enorme_e_limitado_em_memoria_e_na_persistencia` | 2 MB de `conteudo_bruto` não são persistidos inteiros |
| `test_limpar_html_para_texto_e_limitado_antes_de_materializar` | o HTML cortado chega **antes** da limpeza (≤ 8× o teto), não 3 MB |
| `test_busca_rss_limita_campos_grandes_no_caminho_do_provider` | item de RSS com título/URL gigantes não sai do `buscar_itens` |
| `test_url_acima_do_limite_e_descartada_pelo_provider_e_registrada` | descarte com log de WARNING (fonte + tamanho + limite) |
| `test_imagem_url_acima_do_limite_e_descartada_pelo_provider` | imagem zerada, item entra |
| `test_tetos_do_provider_batem_com_o_modelo` | **trava de não-drift**: os números locais do provider = `max_length` real do modelo |

### Dois testes existentes foram atualizados

Ambos assertavam `pytest.raises(RuntimeError)` — isto é, codificavam o defeito que
este item veio corrigir. As **invariantes** que eles protegiam foram preservadas e
reafirmadas:

* `test_validator_nao_avanca_se_a_persistencia_do_lote_falhar` — agora verifica
  que a falha foi isolada **e** que o `ETag` **não** avançou (guarda de perda de
  dados), com o log explicando o porquê.
* `test_custo_llm_e_reservado_antes_da_chamada_e_sobrevive_a_queda` — agora
  verifica que a reserva de custo de 0,25 USD **sobreviveu** à queda e que a
  falha foi registrada.

## 4. Verificação

* `pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80` →
  **508 passed**, cobertura **89,30%** (`p1-01-suite-completa-depois.txt`).
  Base antes das mudanças: 476 passed.
* `manage.py check` → `System check identified no issues (0 silenced).`
* `scripts/release/verificar-proveniencia.sh` sha256 =
  `133408e55076f4c71fa439ee2588d94b55f540e4d29da3296d0858bd592a9541` (inalterado).
* Banco de teste: **PostgreSQL 16 real** (o mesmo engine do CI), porque
  `SQLite` ignora `varchar(N)` e portanto **não reproduz** o `DataError`. Com
  SQLite a medicao seria falsa.

## 5. Fora do escopo (e por quê)

* **Admin/API escrevendo `NewsItem` direto** (`catalogo_noticias/admin.py`) não
  passa por `services/limites`. O item é de *ingestão*; o backstop cobre o
  pipeline, não um `ModelForm` do admin. Limitador de form é um item separado.
* **Migrations**: nenhuma criada nem alterada. O placar de item/grupo reaproveita
  o `JSONField erros_por_fonte`, que já existe e já é exposto no admin e na API.
* **`autor` e `tags`** (`NewsItem`) não são preenchidos pela ingestão hoje; entram
  na política de limites para completude do modelo, sem caminho de escrita.
