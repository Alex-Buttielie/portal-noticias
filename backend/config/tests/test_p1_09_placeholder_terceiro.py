"""
Guarda de regressão do item A10 (D3): o placeholder de imagem era um host
de TERCEIRO e saía antes do consentimento. ENCERRADO — agora é local.

A HISTÓRIA DESTE ARQUIVO, EM UMA PARÁGRAFA
==========================================
`lib/imagens.ts` gerava a foto de exemplo em `https://picsum.photos/seed/…`.
`picsum.photos` é serviço de terceiro, e o HTML já servido pelo SSR trazia o
host: a conexão saía antes de qualquer JavaScript rodar, e também para quem
não executa JS. Um lote anterior mediu 42 conexões na home, 6 na página de
categoria e 6 na de artigo, e registrou a pendência como DECISÃO DE PRODUTO
(asset local × portão de consentimento), porque as duas saídas têm
consequências opostas de design.

A decisão foi o asset local. O que este arquivo garante agora é que essa
decisão CONTINUA VALENDO — não que ela foi tomada. A prova de que a
variação do `seed` sobreviveu é comportamental e mora no frontend
(`frontend/testes/placeholder.test.mjs`, executado por `npm test`); aqui o
que se prende é a forma do código e a medição versionada.

POR QUE ISTO É UMA GUARDA E NÃO UM COMENTÁRIO
=============================================
A decisão está escrita em `lib/imagens.ts`, e um comentário não segura nada:
sobrevive à refatoração e some no primeiro "ajuste rápido". Comentário
afirmando "placeholder local" é tão verificável quanto o que afirmava antes
— "é sempre uma URL do próprio portal" — que era falso.

O QUE ESTE ARQUIVO EXIGE
========================
1. FATO: nenhum fonte que produz `src` de imagem no frontend emite host de
   terceiro, e o host que já foi o placeholder é recusado mesmo quando vem
   do RSS.
2. REGISTRO: a decisão continua nomeando o host que encerrou e o número
   medido — que agora é zero.
3. MEDIÇÃO: a evidência versionada do HTML servido tem ZERO conexões para
   host externo de imagem — e o zero não pode vir de um HTML sem imagem
   nenhuma, que é o modo barato de um teste verde e cego.
4. GUARDA: a guarda de consentimento não volta a mentir ("nada externo") nem
   volta a anunciar uma exceção que deixou de existir.
5. AUTOTESTES: as regras de varredura reprovam casos sintéticos. Guarda que
   nunca falha não é guarda.

O QUE ELE NÃO FAZ
==================
Não julga a foto que o RSS traz (`imagem_url` de veículo). Isso é conteúdo,
não placeholder, e é uma decisão de produto diferente — ver o fim de
`lib/imagens.ts`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

IMAGENS = "frontend/lib/imagens.ts"
PLACEHOLDER = "frontend/lib/placeholder.ts"
GUARDA_CONSENTIMENTO = "frontend/scripts/verificar-consentimento-anuncios.mjs"
COMPONENTE_IMAGEM = "frontend/components/ImagemNoticia.tsx"
EVIDENCIA = "backend/config/tests/evidencia_a10_tags.html"

#: Host que era o placeholder. Declarado aqui para que a recontagem da
#: evidência e a varredura de fonte aim no MESMO host que o código declara.
HOST_PLACEHOLDER = "picsum.photos"

#: Hosts que são IDENTIFICADORES (namespace de SVG, contexto de JSON-LD),
#: nunca requisitados. Não entram na contagem de conexão.
NAO_E_CONEXAO = {"www.w3.org", "schema.org"}

#: Esquemas que não abrem conexão: não têm host e não têm rede. O placeholder
#: local é um `data:` URI — contá-lo como "externo" seria o erro invertido,
#: tão grave quanto o original.
SEM_REDE = ("data:", "blob:", "about:", "javascript:")

#: Marcas que indicam que um arquivo produz `src` de imagem. A varredura de
#: host externo só olha arquivos assim — porque `lib/` tem também fetch de API
#: (ViaCEP, IBGE, Nominatim) e Google OAuth, que são chamadas que o próprio
#: frontend faz e NÃO são "imagem de terceiro" (ver o fim de `lib/imagens.ts`).
MARCA_IMAGEM = ("<img", "ImagemNoticia", "placeholderSvg", "imagemNoticia", "imagem_url")

#: Hosts que são o PRÓPRIO PORTAL em desenvolvimento. Não são "imagem de
#: terceiro" — `lib/api.ts` declara `localhost:8000` como base da API, e é o
#: backend do próprio projeto atendendo. Um teste que acusasse isso faria a
#: guarda ser desligada por ruído, que é como uma guarda deixa de proteger.
HOST_PROPRIO = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

RAIZ = Path(__file__).resolve().parents[3]


def _fonte(rel: str) -> str:
    return (RAIZ / rel).read_text(encoding="utf-8")


def _sem_comentarios(fonte: str) -> str:
    """
    Remove comentários, sem destruir URL.

    O cuidado aqui NÃO é teórico: o regex ingênuo `//.*$` casa o `//` de
    `https://picsum.photos/...` e passa a "comentar" a partir dali,
    apagando o próprio host que a guarda existe para contar. Foi
    exatamente o que aconteceu na primeira versão deste arquivo, e o
    sintoma foi o pior possível — os autotestes davam 0 para um fonte que
    a própria guarda contava como tendo o host — e a guarda ficava verde
    sem ver nada.

    Por isso o `//` só conta como comentário quando NÃO é precedido por
    `:` — o que separa URL de comentário de linha.
    """
    fonte = re.sub(r"/\*.*?\*/", "", fonte, flags=re.DOTALL)
    return re.sub(r"(?m)(?<!:)//.*$", "", fonte)


def _conexoes_para_host_de_imagem(html: str, host: str = HOST_PLACEHOLDER) -> int:
    """
    Conta as conexões que um browser REAL faria para `host` a partir de um
    HTML servido, sem consentimento dado.

    Deliberadamente conta o que o browser BUSCA, não o que o texto
    menciona:
      - `src` de `<img>`, `<script>` e `<iframe>` => 1 conexão cada;
      - `href`/`imageSrcSet` de `<link rel=preload|prefetch|preconnect|
        dns-prefetch>` => 1;
      - `srcset` de `<img>` NÃO conta: são candidatos, e o browser baixa
        UM por tag. Contar srcset inflaria o número várias vezes — e foi
        uma contagem inflada que deixou "externas: 0" passar despercebido.
    """
    h = re.escape(host)
    conexoes = 0
    tags = re.findall(r"<(?:img|link|script|iframe)\b[^>]*>", html, re.IGNORECASE)
    for tag in tags:
        if re.match(r"<(?:img|script|iframe)\b", tag, re.IGNORECASE):
            # Esquema opcional (`https://host/`, `//host/` ou `host/`): o
            # atributo pode vir completo ou relativo ao protocolo.
            conexoes += len(re.findall(rf'\ssrc="(?:https?:)?(?://)?{h}/', tag))
        elif re.match(r"<link\b", tag, re.IGNORECASE):
            if re.search(r'\srel="[^"]*(?:preload|prefetch|preconnect|dns-prefetch)', tag):
                conexoes += len(
                    re.findall(rf'(?:href|imageSrcSet)="[^"]*(?:https?:)?(?://)?{h}', tag)
                )
    return conexoes


def _resolver_constantes(fonte: str) -> str:
    """
    Substitui referência a constante pelo VALOR, para que a busca de host
    enxergue a URL montada por TEMPLATE.

    POR QUE ESTA FUNÇÃO EXISTE, E O QUE ELA JÁ PEGOU
    ================================================
    `lib/imagens.ts` declara o host numa constante e o interpola:

        export const HOST_PLACEHOLDER = "picsum.photos";
        const picsum = (s) => `https://${HOST_PLACEHOLDER}/seed/${s}/800/450`;

    Um `re.findall(r"https?://([A-Za-z0-9.-]+)")` NÃO enxerga isso: depois
    do `https://` vem um `$`, que não é caractere de host — a regex simply
    não casa, e a guarda passa.

    Isto não é teórico: foi MEDIDO nesta run. Reverter o placeholder para a
    URL externa por template deixou verdes TODAS as guardas ao mesmo tempo —
    a de consentimento, os 24 testes de Python e os 40 de Node. Verde e cego
    é o pior estado possível para uma guarda, e era exatamente o estado que a
    pendência deste item dizia impedir.

    A interpolação é resolvida nos dois formatos que aparecem em JS:
    `${CONSTANTE}` dentro de template, e a constante sozinha.
    """
    fonte = fonte.replace("${HOST_PLACEHOLDER}", HOST_PLACEHOLDER)
    return fonte.replace("HOST_PLACEHOLDER", HOST_PLACEHOLDER)


def _hosts_de_imagem_do_codigo() -> dict[str, set[str]]:
    """Host http(s) por fonte, com as constantes resolvidas."""
    achados: dict[str, set[str]] = {}
    for caminho in _arquivos_que_produzem_imagem():
        fonte = _resolver_constantes(
            _sem_comentarios(caminho.read_text(encoding="utf-8", errors="replace"))
        )
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", fonte))
        externos = {h for h in hosts if h not in NAO_E_CONEXAO and h not in HOST_PROPRIO}
        if externos:
            achados[str(caminho.relative_to(RAIZ))] = externos
    return achados


def _arquivos_que_produzem_imagem() -> list[Path]:
    """Fontes do frontend que podem acabar virando `src` de `<img>`."""
    achados = []
    for padrao in ("*.ts", "*.tsx"):
        for caminho in sorted((RAIZ / "frontend").rglob(padrao)):
            if "node_modules" in caminho.parts or ".next" in caminho.parts:
                continue
            texto = caminho.read_text(encoding="utf-8", errors="replace")
            if any(marca in texto for marca in MARCA_IMAGEM):
                achados.append(caminho)
    return achados


# ---------------------------------------------------------------------------
# 1. O FATO: o placeholder é local
# ---------------------------------------------------------------------------
class TestPlaceholderEhLocal:
    def test_nenhum_fonte_de_imagem_emite_host_de_terceiro(self):
        """
        O fato, na forma que não pode ser contornada, e na amplitude certa:
        TODO arquivo do frontend que pode virar `src` de `<img>` é varrido,
        não só `lib/imagens.ts`.

        Este teste existia INVERTIDO no lote anterior (mesma forma, exigindo
        o host de terceiro). Aqui exige a ausência dele. A amplitude é o
        ponto: um teste que só olha `lib/imagens.ts` passa enquanto
        `ImagemNoticia` — que tem a própria allowlist — aponta para um
        terceiro por outro caminho.

        A busca é feita em duas passadas porque `lib/imagens.ts` declara o
        host numa CONSTANTE (`HOST_PLACEHOLDER`) e o interpola nos
        templates. Uma varredura que procurasse só o host literal passaria a
        não ver NADA depois dessa refatoração — verde e cega, que é o pior
        estado possível para uma guarda.
        """
        infratores = _hosts_de_imagem_do_codigo()
        assert not infratores, (
            f"fonte que produz imagem voltou a emitir host externo: {infratores}. "
            "O placeholder tem de ser gerado localmente (`lib/placeholder.ts`)."
        )

    def test_a_varredura_de_host_enxerga_url_montada_por_template(self):
        """
        Autoteste do buraco que ESTA run encontrou e fechou.

        O caso: `https://${HOST_PLACEHOLDER}/seed/...`. O `https://` é
        seguido de `$`, que não casa com `[A-Za-z0-9.-]+` — a regex de host
        não via nada, e a guarda passa. Foi o que aconteceu quando o
        placeholder foi revertido para a URL externa por template: 24 testes
        de Python verdes, 40 de Node verdes, guarda de consentimento verde.

        Este teste existe para que a resolução de constante não seja
        removida como "refactoração" — ela é o que dá poder discriminante
        à guarda, e a prova de que ela funciona é que ela REPROVA.
        """
        fonte_sintetico = (
            'export const HOST_PLACEHOLDER = "picsum.photos";\n'
            "const picsum = (seed: string) =>\n"
            "  `https://${HOST_PLACEHOLDER}/seed/${encodeURIComponent(seed)}/800/450`;\n"
        )
        hosts = set(
            re.findall(
                r"https?://([A-Za-z0-9.-]+)",
                _resolver_constantes(_sem_comentarios(fonte_sintetico)),
            )
        )
        assert HOST_PLACEHOLDER in hosts, (
            "a resolução de constante parou de funcionar: um host montado "
            "por template passou a ser invisível para a varredura, e a "
            "guarda volta a ser verde sem ver nada"
        )
        # E o porquê: a busca SEM resolver não acha nada. Se um dia achar, é
        # porque a regex mudou, e este teste precisa ser revisto.
        sem_resolver = set(
            re.findall(
                r"https?://([A-Za-z0-9.-]+)", _sem_comentarios(fonte_sintetico)
            )
        )
        assert HOST_PLACEHOLDER not in sem_resolver, (
            "a busca de host passou a enxergar template sem resolução; "
            "confirme que a resolução de constante continua necessária"
        )

    def test_o_placeholder_e_um_data_uri(self):
        """
        `data:` é a prova de que não há requisição. Um SVG em arquivo local
        seria aceitável como design, mas exigiria uma conexão por imagem — e
        a guarda não pode dizer "zero saída externa de imagem" se o desenho
        ainda sai pela rede.
        """
        fonte = _sem_comentarios(_fonte(PLACEHOLDER))
        assert "data:image/svg+xml" in fonte, (
            "o placeholder deixou de ser embutido no HTML; um SVG servido por "
            "URL continua sendo uma requisição por imagem"
        )
        # `xmlns='http://www.w3.org/2000/svg'` é IDENTIFICADOR (o namespace
        # do SVG), não host requisitado — por isso `NAO_E_CONEXAO`. Qualquer
        # OUTRO host, sim, é conexão de terceiro.
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", fonte))
        assert not (hosts - NAO_E_CONEXAO), (
            f"o gerador do placeholder passou a conter host externo: "
            f"{sorted(hosts - NAO_E_CONEXAO)}"
        )

    def test_o_host_do_placeholder_antigo_e_recusado_no_caminho_do_rss(self):
        """
        Fechar o item exige fechar os DOIS caminhos.

        O placeholder local resolve o caminho "notícia sem `imagem_url`".
        Mas `imagem_url` vem do XML do RSS: um feed apontando para
        `picsum.photos` reconecta o terceiro por dentro da allowlist de
        esquema (que aceita http/https, e com razão). Por isso a recusa
        explícita do host.
        """
        fonte = _fonte(IMAGENS)
        assert f'"{HOST_PLACEHOLDER}"' in fonte, (
            "o host do placeholder antigo sumiu da allowlist; sem a recusa "
            "explícita um `imagem_url` de RSS volta a pedir a um terceiro"
        )
        assert "ehHostDePlaceholder" in fonte, (
            "a função que recusa o host sumiu de `lib/imagens.ts`"
        )
        assert "urlImagemUtilizavel" in _fonte(COMPONENTE_IMAGEM), (
            "`ImagemNoticia` deixou de usar a função que recusa o host — e ela "
            "é quem recebe `imagem_url` cru, direto do feed"
        )

    def test_a_decisao_esta_escrita_com_o_numero_medido_zero(self):
        """
        O que se prende não é a prosa, é a EXISTÊNCIA do registro: decisão
        tomada, host antigo nomeado, e o número medido escrito.

        Um encerramento sem número é um encerramento que ninguém confere
        depois — e "ninguém confere" é como a pendência volta.
        """
        fonte = _fonte(IMAGENS)
        assert HOST_PLACEHOLDER in fonte, "a decisão deixou de nomear o host que ela encerrou"
        numeros = re.findall(r"\b(\d+)\s+conex", fonte, re.IGNORECASE)
        assert numeros, "o registro ficou sem o número medido de conexões"

        # A coluna da DIREITA do quadro `antes -> depois` é o estado atual e
        # tem de ser zero. O número ANTES (o 61) é histórico do que foi
        # medido, e apagá-lo seria apagar a única prova de que o problema
        # existia — por isso a comparação é posicional, não "todo número".
        depois = re.findall(r"(\d+)\s*->\s*(\d+)\s*conex", fonte)
        assert depois, (
            "o registro ficou sem o quadro `antes -> depois` de conexões; "
            "sem ele não há como ler o que a decisão mudou"
        )
        for antes, agora in depois:
            assert int(agora) == 0, (
                f"o quadro declara {agora} conexões depois da decisão "
                f"(antes: {antes}). Depois do asset local não pode sobrar "
                "nenhuma, e o número errado aqui é o número que a guarda "
                "vai acabar repetindo."
            )

    def test_nenhuma_afirmacao_de_url_nosso_sobre_o_placeholder(self):
        """
        Regressão do comentário falso, agora sobre a frase que o produziu.

        O defeito original era um comentário que dizia "que é sempre uma URL
        do próprio portal". Um teste que lê comentário é frágil — o
        comentário pode ser reescrito. O que este teste prende é a
        CONSEQUÊNCIA: nenhum código-executando do frontend pode afirmar que
        o placeholder é host do portal.
        """
        infratores = []
        for caminho in sorted((RAIZ / "frontend").rglob("*.ts")):
            if "node_modules" in caminho.parts:
                continue
            texto = _sem_comentarios(
                caminho.read_text(encoding="utf-8", errors="replace")
            ).lower()
            for frase in ("url do próprio portal", "url nossa", "url do proprio portal"):
                if frase in texto:
                    infratores.append(f"{caminho.relative_to(RAIZ)}: {frase}")
        assert not infratores, (
            f"código afirma que o placeholder é host do próprio portal: {infratores}."
        )

    def test_o_componente_trata_o_placeholder_como_local(self):
        """
        `ImagemNoticia` é quem consome o gerador e quem conhece o fluxo do
        browser. Ela precisa dizer LOCAL — se voltar a chamar o placeholder
        de terceiro, a próxima pessoa que mexer na cadeia de fallback
        reintroduz a conexão.
        """
        fonte = _fonte(COMPONENTE_IMAGEM).lower()
        assert "url do próprio portal" not in fonte
        assert "url do proprio portal" not in fonte
        assert "placeholder local" in fonte, (
            "`ImagemNoticia` deixou de dizer que o placeholder é local"
        )
        # E não pode continuar pedindo `srcset` do gerador antigo: não há mais
        # candidata para escolher, e o SVG escala para qualquer largura.
        assert "srcSetPicsum" not in fonte and "picsum(" not in fonte, (
            "`ImagemNoticia` ainda chama o gerador antigo de srcSet"
        )


# ---------------------------------------------------------------------------
# 2. A MEDIÇÃO
# ---------------------------------------------------------------------------
class TestMedicaoDaPendencia:
    def test_a_medicao_conta_o_que_o_browser_busca(self):
        """
        A regra de contagem, exercitada contra um HTML sintético.

        Sem isto, a contagem é um número que ninguém sabe reproduzir, e um
        número que ninguém sabe reproduzir é exatamente o tipo de coisa que
        vira "externas: 0" quando convém.
        """
        html = (
            '<img src="https://picsum.photos/seed/a/800/450" loading="lazy">'
            '<img src="https://picsum.photos/seed/b/800/450" loading="eager">'
            '<link rel="preload" as="image" imageSrcSet="https://picsum.photos/seed/c/800/450 800w">'
            '<link rel="preconnect" href="https://picsum.photos">'
            '<img src="https://exemplo.com/foto.jpg" srcset="https://picsum.photos/seed/d/400/225 400w">'
        )
        # 2 <img src> + 1 preload + 1 preconnect = 4.
        # O srcset do <img> de outro host NÃO conta: é candidato, e o browser
        # só o buscaria se escolhesse aquele src — o que ele não faz.
        assert _conexoes_para_host_de_imagem(html) == 4

    def test_html_sem_placeholder_da_zero(self):
        html = (
            '<img src="https://exemplo.com/a.jpg">'
            '<link rel="preconnect" href="https://fonts.exemplo">'
        )
        assert _conexoes_para_host_de_imagem(html) == 0

    def test_data_uri_nao_conta_como_conexao(self):
        """
        O erro INVERTIDO, e tão grave quanto o original.

        O placeholder local É um `data:` URI e aparece em cada `<img>` da
        página. Uma regra que contasse data URI como conexão externa
        reportaria dezenas de "externas" para uma página que não fez uma
        requisição sequer — e o time aprenderia a ignorar o número.
        """
        html = (
            '<img src="data:image/svg+xml,%3Csvg%3E%3C/svg%3E">'
            '<img src="data:image/svg+xml,%3Csvg%3E%3C/svg%3E">'
            '<link rel="preload" as="image" imageSrcSet="data:image/svg+xml,%3Csvg%3E">'
        )
        assert _conexoes_para_host_de_imagem(html) == 0
        for esquema in SEM_REDE:
            assert not esquema.startswith(("http://", "https://")), (
                f"'{esquema}' foi listado como conexão externa"
            )

    def test_a_evidencia_da_zero_conexao_externa_de_imagem(self):
        """
        A medição deste lote, refeita contra o HTML servido.

        Este é o teste que impede o "zero" de virar ficção: ele reconta as
        conexões a partir do HTML de produção que este repositório versiona
        como evidência, e exige que o número seja zero.
        """
        evidencia = RAIZ / EVIDENCIA
        assert evidencia.exists(), (
            "a evidência da medição sumiu do repositório. Sem ela o zero não "
            "é reproduzível, e um zero não reproduzível é justamente o que "
            "vira 'externas: 0'."
        )
        conexoes = _conexoes_para_host_de_imagem(evidencia.read_text(encoding="utf-8"))
        assert conexoes == 0, (
            f"a evidência versionada tem {conexoes} conexões para "
            f"{HOST_PLACEHOLDER}; o número que `lib/imagens.ts` declara é 0. "
            "Uma das duas está errada — e uma delas está errada de um jeito "
            "que não se vê rodando a suíte."
        )

    def test_o_zero_da_evidencia_nao_veio_de_uma_pagina_sem_imagem(self):
        """
        A armadilha do "zero" mais barata: uma evidência sem nenhuma imagem
        dá zero conexões e o teste passa — sem nunca ter olhado para o
        portal. A evidência tem que CONTER as imagens de placeholder, e elas
        precisam ser DISTINTAS entre si.

        Nenhum dos dois lados é sku: as imagens que a evidência mostra são as
        que o portal realmente emite, incluindo as `data:` (placeholder local)
        e as do host do veículo (foto do RSS), que são conteúdo e estão fora
        do escopo desta medição. O que NÃO pode existir é uma imagem apontando
        para um host que não seja nenhum dos dois.
        """
        evidencia = (RAIZ / EVIDENCIA).read_text(encoding="utf-8")
        imgs = re.findall(r"<img\b[^>]*>", evidencia, re.IGNORECASE)
        assert len(imgs) >= 5, (
            f"a evidência tem só {len(imgs)} <img>; um 'zero' assim é "
            "vazio, não medido"
        )

        placeholders = [t for t in imgs if "data:image/svg+xml" in t]
        conteudo = [t for t in imgs if "data:image/svg+xml" not in t]
        assert len(placeholders) >= 5, (
            f"só {len(placeholders)} <img> de placeholder local em "
            f"{len(imgs)}; o placeholder não está no HTML servido"
        )

        # Toda imagem é OU placeholder local OU foto de conteúdo. Se sobrar
        # uma terceira coisa, ela é host de terceiro e o "zero" é ficção.
        extranhos = [t for t in conteudo if not re.search(r'\ssrc="https?://', t)]
        assert not extranhos, (
            f"{len(extranhos)} <img> da evidência com src fora do padrão "
            f"placeholder-local ou host-de-conteúdo: {extranhos[:3]}"
        )

        assert len(set(placeholders)) >= 3, (
            f"só {len(set(placeholders))} imagens distintas em "
            f"{len(placeholders)} posições: a variação não sobreviveu"
        )


# ---------------------------------------------------------------------------
# 3. A GUARDA DE CONSENTIMENTO NÃO PODE MENTIR (NEM PARA BAIXO)
# ---------------------------------------------------------------------------
class TestGuardaDeConsentimentoNaoDizNadaExterno:
    def test_a_saida_da_guarda_nao_afirma_nada_externo(self):
        """
        A mesma doença, no lugar onde ela se escondia melhor.

        A guarda de consentimento varrida `REGEX_HOST_EXTERNO`, que só
        conhece host de ANÚNCIO e MEDIÇÃO, e imprimia na saída "nada
        externo antes do consentimento". Com o picsum na tela, essa frase é
        falsa — e é a frase que fazia o número de externos desaparecer.

        Só o que a guarda EXECUTA é lido: o arquivo também tem comentários
        que CITAM a frase removida para explicar a remoção, e um teste que
        lê comentário se acusa sozinho.
        """
        fonte = _sem_comentarios(_fonte(GUARDA_CONSENTIMENTO)).lower()
        assert "nada externo antes do consentimento" not in fonte, (
            "a guarda voltou a afirmar 'nada externo antes do consentimento'. "
            "O que ela prova é sobre ANÚNCIO e MEDIÇÃO — escreva isso."
        )

    def test_a_guarda_nao_declara_mais_a_excecao_de_imagem(self):
        """
        A exceção era um `ATENÇÃO` na saída, porque a imagem era de terceiro.

        Com o asset local, manter esse `ATENÇÃO` seria ruído que treina o
        leitor a ignorar a palavra — e é a palavra que faz a diferença entre
        "olha, tem um problema conhecido" e "olha, isto está resolvido".
        """
        fonte = _sem_comentarios(_fonte(GUARDA_CONSENTIMENTO))
        assert "ATENCAO" not in fonte and "ATENÇÃO" not in fonte, (
            "a guarda continua anunciando a exceção de imagem; o placeholder "
            "é local e a exceção deixou de existir"
        )

    def test_a_guarda_afirma_o_que_ela_mede(self):
        """
        O sim da mesma honestidade: depois do asset local, a guarda PODE dizer
        o que mediu, porque não há nada de fora para omitir.

        Uma guarda que só sabe dizer "não afirmo nada externo" aprende a
        esconder defeito; esta tem que dizer o que provou.
        """
        fonte = _sem_comentarios(_fonte(GUARDA_CONSENTIMENTO)).lower()
        assert "imagem" in fonte, (
            "a guarda deixou de falar de imagem; sem isso ela não afirma "
            "nada sobre o caminho que este lote conserta"
        )
        assert "local" in fonte, (
            "a guarda precisa dizer que a imagem é servida localmente — é "
            "isso que fecha o item"
        )

    def test_a_guarda_inventaria_o_host_de_terceiro(self):
        """
        O inventário A10 tem que existir e mirar o host certo.

        Continua existindo MESMO com o código limpo: é o que faria a guarda
        reprovar sozinha no dia em que alguém reintroduzir o host, em vez de
        esperar este arquivo de teste rodar.
        """
        fonte = _fonte(GUARDA_CONSENTIMENTO)
        assert "A10" in fonte, "o inventário de saída externa de imagem sumiu da guarda"
        assert "picsum" in fonte, "o inventário não aponta para o host de terceiro conhecido"

    def test_a_guarda_nao_declara_vazio_o_que_sabe_que_existe(self):
        """
        Autoteste da honestidade do inventário: um fonte QUE TEM placeholder
        não pode ser reportado como "nenhum placeholder de terceiro".
        """
        fonte = _sem_comentarios(_fonte(GUARDA_CONSENTIMENTO))
        assert (
            "fontesComPlaceholder.length > 0" in fonte
            or "fontesComPlaceholder.length>0" in fonte
        ), (
            "o inventário não decide por contagem — ele pode reportar "
            "'nenhum' sobre um fonte que tem placeholder"
        )


# ---------------------------------------------------------------------------
# 4. AUTOTESTES DAS REGRAS DE VARREDURA
# ---------------------------------------------------------------------------
class TestVarreduraDoPlaceholder:
    @pytest.mark.parametrize(
        "fonte,esperado",
        [
            ("const u = `https://picsum.photos/seed/x/800/450`;", 1),
            ("// picsum.photos/seed/x\nconst u = 1;", 0),
            ("/* picsum.photos */ const u = 1;", 0),
            (
                "const u = 'https://picsum.photos/seed/a/1/1' + "
                "'https://picsum.photos/seed/b/2/2';",
                2,
            ),
        ],
    )
    def test_conta_referencia_de_codigo_e_nao_comentario(self, fonte, esperado):
        achados = re.findall(
            r"(?:https?://)?(?:www\.)?picsum\.photos/", _sem_comentarios(fonte)
        )
        assert len(achados) == esperado


class TestStripperNaoQuebraURL:
    """
    A primeira versão desta guarda usava `//.*$` para remover comentários e
    ele APAGAVA o `//` de `https://...` — ou seja, a guardava por um host
    que ela mesma destruía. O sintoma era silencioso (contava 0) e o
    resultado era uma guarda verde que não via nada.

    Estes casos existem para que isso não volte.
    """

    def test_url_sobrevive_ao_strip_de_comentario_de_linha(self):
        limpo = _sem_comentarios("const u = 'https://picsum.photos/seed/x/1/1';")
        assert "picsum.photos" in limpo

    def test_comentario_de_linha_real_e_removido(self):
        assert "picsum" not in _sem_comentarios("// picsum.photos\nconst u = 1;")

    def test_comentario_de_bloco_e_removido(self):
        assert "picsum" not in _sem_comentarios("/* picsum.photos */\nconst u = 1;")

    def test_url_antes_e_depois_de_comentario(self):
        fonte = (
            "const a = 'https://picsum.photos/1/1';\n"
            "// nota\n"
            "const b = 'https://picsum.photos/2/2';"
        )
        assert _sem_comentarios(fonte).count("picsum.photos") == 2