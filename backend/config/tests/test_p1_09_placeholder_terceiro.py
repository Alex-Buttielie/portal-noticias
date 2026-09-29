"""
Guarda de regressão para a PENDÊNCIA A10 (D3): o placeholder de imagem
é um host de TERCEIRO e sai antes do consentimento.

POR QUE ISTO É UMA GUARDA E NÃO UM COMENTÁRIO
==============================================
A pendência está escrita em `lib/imagens.ts`, e um comentário não segura
nada: sobrevive à refatoração e some no primeiro "ajuste rápido". O que
este arquivo faz é tornar o FATO legível por qualquer pessoa que rode a
guarda, e impedir que a frase "nada externo antes do consentimento" volte
a ser imprimida como se fosse verdade.

O QUE ESTE TESTO NÃO FAZ
========================
Não reprova. A correção do placeholder é DECISÃO DE PRODUTO (asset local
versus passar atrás do portão de consentimento) e as duas consequências de
design são opostas — nenhuma delas é escolha de engenharia. Reprovar aqui
seria o executor decidindo o produto por conta própria.

O QUE ELE FAZ
=============
1. Mede: conta as conexões que um browser real faria, e devolve o número.
2. Não deixa mentir: enquanto o placeholder existir, a saída da guarda de
   consentimento NÃO pode dizer "nada externo antes do consentimento".
3. Se autotesta: as regras de varredura precisam reprovar casos sintéticos.
   Guarda que nunca falha não é guarda.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

IMAGENS = "frontend/lib/imagens.ts"
GUARDA_CONSENTIMENTO = "frontend/scripts/verificar-consentimento-anuncios.mjs"
COMPONENTE_IMAGEM = "frontend/components/ImagemNoticia.tsx"

#: Hosts que são IDENTIFICADORES (namespace de SVG, contexto de JSON-LD),
#: nunca requisitados. Não entram na contagem de conexão.
NAO_E_CONEXAO = {"www.w3.org", "schema.org"}

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
    própria guarda contando 0 para um fonte que tem o host — e a
    guarda ficava verde sem ver nada.

    Por isso o `//` só conta como comentário quando NÃO é precedido por
    `:` — o que separa URL de comentário de linha.
    """
    fonte = re.sub(r"/\*.*?\*/", "", fonte, flags=re.DOTALL)
    return re.sub(r"(?m)(?<!:)//.*$", "", fonte)


def _conexoes_para_picsum(html: str) -> int:
    """
    Conta as conexões que um browser REAL faria para `picsum.photos` a
    partir de um HTML servido, sem consentimento dado.

    Deliberadamente conta o que o browser BUSCA, não o que o texto
    menciona:
      - `src` de `<img>`, `<script>` e `<iframe>` => 1 conexão cada;
      - `href`/`imageSrcSet` de `<link rel=preload|prefetch|preconnect|
        dns-prefetch>` => 1;
      - `srcset` de `<img>` NÃO conta: são candidatos, e o browser baixa
        UM por tag. Contar srcset inflaria o número várias vezes — e foi
        uma contagem inflada que deixou "externas: 0" passar despercebido.
    """
    conexoes = 0
    tags = re.findall(r"<(?:img|link|script|iframe)\b[^>]*>", html, re.IGNORECASE)
    for tag in tags:
        if re.match(r"<(?:img|script|iframe)\b", tag, re.IGNORECASE):
            conexoes += len(re.findall(r'\ssrc="https://picsum\.photos/', tag))
        elif re.match(r"<link\b", tag, re.IGNORECASE):
            if re.search(r'\srel="[^"]*(?:preload|prefetch|preconnect|dns-prefetch)', tag):
                conexoes += len(re.findall(r'(?:href|imageSrcSet)="[^"]*picsum\.photos', tag))
    return conexoes


# ---------------------------------------------------------------------------
# 1. O FATO
# ---------------------------------------------------------------------------
class TestPendenciaA10PlaceholderEhDeTerceiro:
    def test_o_placeholder_aponta_para_um_host_de_terceiro(self):
        """
        Se um dia o placeholder virar local, este teste avisa — e a
        pendência precisa ser reescrita, não apagada em silêncio.

        A busca é feita em duas passadas porque `lib/imagens.ts` declara o
        host numa CONSTANTE (`HOST_PLACEHOLDER`) e a interpola nos
        templates. Uma guarda que procurasse só o host literal passaria a
        não ver NADA depois dessa refatoração — verde e cega, que é o pior
        estado possível para uma guarda.
        """
        fonte = _sem_comentarios(_fonte(IMAGENS))
        resolvido = fonte.replace("HOST_PLACEHOLDER", '"picsum.photos"')
        hosts = set(re.findall(r"https?://([A-Za-z0-9.-]+)", fonte))
        hosts |= set(re.findall(r"https?://([A-Za-z0-9.-]+)", resolvido))
        externos = {h for h in hosts if h not in NAO_E_CONEXAO}
        assert externos, "nenhum host externo no gerador de imagem — a pendência mudou de forma?"
        assert "picsum.photos" in externos, (
            f"o host do placeholder mudou para {externos}; atualize a pendência "
            "e a medição em `lib/imagens.ts`."
        )

    def test_a_pendencia_esta_escrita_e_classificada(self):
        """
        O que se prende não é a prosa do texto, é a EXISTÊNCIA da
        classificação: pendência presente, dizendo que o host é de terceiro
        e que a correção é decisão de produto.
        """
        fonte = _fonte(IMAGENS)
        assert "PENDÊNCIA" in fonte, "a pendência do placeholder sumiu de `lib/imagens.ts`"
        assert "TERCEIRO" in fonte, "a pendência deixou de dizer que o host é de terceiro"
        assert "DECISÃO DE PRODUTO" in fonte, "a pendência deixou de classificar a correção"

    def test_nenhuma_afirmacao_de_url_nosso_sobre_o_placeholder(self):
        """
        Regressão do comentário falso, agora sobre a frase que o produziu.

        O defeito original era um comentário que dizia "que é sempre uma URL
        do próprio portal". Um teste que lê comentário é frágil — o
        comentário pode ser reescrito. O que este teste prende é a
        CONSEQUÊNCIA: nenhum código-executando do frontend pode afirmar que
        o placeholder é host do portal. A PENDÊNCIA cita a frase para
        explicar que ela era falsa, e por isso é ignorada aqui.
        """
        infratores = []
        for caminho in sorted((RAIZ / "frontend").rglob("*.ts")):
            if "node_modules" in caminho.parts:
                continue
            texto = _sem_comentarios(caminho.read_text(encoding="utf-8", errors="replace")).lower()
            for frase in ("url do próprio portal", "url nossa", "url do proprio portal"):
                if frase in texto:
                    infratores.append(f"{caminho.relative_to(RAIZ)}: {frase}")
        assert not infratores, (
            f"código afirma que o placeholder é host do próprio portal: {infratores}. "
            "`picsum.photos` é serviço de terceiro."
        )

    def test_o_componente_nao_afirma_mais_que_e_url_do_portal(self):
        """
        O segundo arquivo que carregava a afirmação falsa.

        Aqui a leitura é do fonte INTEIRO, comentários incluídos, e é por
        isso: a afirmação falsa ERA um comentário, e a verdade que a
        substitui também é. Um teste que limpasse comentários antes de
        procurar a frase estaria olhando o lugar errado — e passaria com o
        defeito intacto.
        """
        fonte = _fonte(COMPONENTE_IMAGEM).lower()
        assert "url do próprio portal" not in fonte
        assert "url do proprio portal" not in fonte
        assert "terceiro" in fonte, (
            "`ImagemNoticia` deixou de dizer que o picsum é serviço de terceiro"
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
        assert _conexoes_para_picsum(html) == 4

    def test_html_sem_placeholder_da_zero(self):
        html = (
            '<img src="https://exemplo.com/a.jpg">'
            '<link rel="preconnect" href="https://fonts.exemplo">'
        )
        assert _conexoes_para_picsum(html) == 0

    def test_a_pendencia_declara_o_numero_medido(self):
        """
        A pendência tem que CONTINUAR com número.

        Um "pendente" sem número é um "pendente" que ninguém prioriza: não
        dá para saber se são 6 conexões ou 6.000, e por isso vira a última
        linha em aberto.
        """
        fonte = _fonte(IMAGENS)
        numeros = re.findall(r"\b(\d+)\s+conex", fonte, re.IGNORECASE)
        assert numeros, "a pendência está sem o número medido de conexões"
        assert any(int(n) > 0 for n in numeros)

    def test_a_medicao_real_confere_com_a_pendencia(self):
        """
        A medição deste lote, refeita contra o HTML servido.

        Este é o teste que impede o número da pendência de virar ficção: ele
        reconta as conexões a partir do HTML de produção que este arquivo
        versiona como evidência, e exige que o número bate.
        """
        evidencia = RAIZ / "backend" / "config" / "tests" / "evidencia_a10_tags.html"
        assert evidencia.exists(), (
            "a evidência da medição sumiu do repositório. Sem ela o número da "
            "pendência não é reproduzível, e um número não reproduzível é "
            "justamente o que vira 'externas: 0'."
        )
        conexoes = _conexoes_para_picsum(evidencia.read_text(encoding="utf-8"))
        fonte = _fonte(IMAGENS)
        declarados = [int(n) for n in re.findall(r"\b(\d+)\s+conex", fonte, re.IGNORECASE)]
        assert conexoes in declarados, (
            f"a medição real dá {conexoes} conexões e a pendência declara "
            f"{declarados}. Uma das duas está desatualizada — e uma delas "
            "está errada, o que é pior que desatualizada."
        )


# ---------------------------------------------------------------------------
# 3. A GUARDA DE CONSENTIMENTO NÃO PODE MENTIR
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

    def test_a_guarda_declara_a_excecao_de_imagem(self):
        fonte = _fonte(GUARDA_CONSENTIMENTO)
        assert "ATENCAO" in fonte or "ATENÇÃO" in fonte, (
            "a guarda precisa dizer explicitamente que a imagem é uma exceção"
        )

    def test_a_guarda_inventaria_o_host_de_terceiro(self):
        """O inventário A10 tem que existir e mirar o host certo."""
        fonte = _fonte(GUARDA_CONSENTIMENTO)
        assert "A10" in fonte, "o inventário de saída externa de imagem sumiu da guarda"
        assert "picsum" in fonte, "o inventário não aponta para o host de terceiro conhecido"

    def test_a_guarda_nao_declara_vazio_o_que_sabe_que_existe(self):
        """
        Autoteste da honestidade do inventário: um fonte QUE TEM placeholder
        não pode ser reportado como "nenhum placeholder de terceiro".
        """
        fonte = _sem_comentarios(_fonte(GUARDA_CONSENTIMENTO))
        assert "fontesComPlaceholder.length > 0" in fonte or "fontesComPlaceholder.length>0" in fonte, (
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
