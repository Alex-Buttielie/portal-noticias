"""
P1-01b — caminho de escrita do **Admin do Django** passa pela politica de
limites (`catalogo_noticias/services/limites.py`).

O P1-01 fechou a injecao de ``<script>`` na INGESTAO. estes testes fecham o
caminho do ADMIN, que era o mesmo defeito: `NewsItemAdmin` so declara
`readonly_fields = ["timestamp_ingestao"]`, logo `titulo` e editavel, e um
POST de changeform com `</script>` no titulo devolvia HTTP 302 e persistia
**byte-identico** (medido; evidencia `docs/evidencias/p101b-prova-antes.txt`).

Os limites aqui NAO sao numeros chutados: sao lidos do proprio modelo
(`_meta.get_field(campo).max_length`), a mesma fonte de verdade do codigo de
producao e dos testes do P1-01. Mudar o `max_length` no modelo muda a
expectativa sem editar este arquivo.

O que cada bloco mede esta escrito no docstring do teste.
"""

from __future__ import annotations

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from catalogo_noticias.admin import NewsClusterAdmin, NewsItemAdmin
from catalogo_noticias.limites_admin import (
    LimitesAdminMixin,
    LimitesModelFormMixin,
    aplicar_limites_no_admin,
)
from catalogo_noticias.models import NewsCluster, NewsItem
from catalogo_noticias.services import limites
from catalogo_noticias.services.limites import CampoForaDoLimiteError

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Limites REAIS do modelo (fonte de verdade, nao numeros chutados)
# ---------------------------------------------------------------------------


def _limite(modelo, campo: str) -> int:
    limite = modelo._meta.get_field(campo).max_length
    assert limite is not None, f"{modelo.__name__}.{campo} nao tem max_length"
    return limite


LIMITE_TITULO = _limite(NewsItem, "titulo")
LIMITE_URL = _limite(NewsItem, "url_fonte_original")
LIMITE_TITULO_CLUSTER = _limite(NewsCluster, "titulo_acontecimento")

TITULO_COM_SCRIPT = (
    "Prefeitura anuncia obra </script><script>alert('XSS-ARMADO')</script>"
)
CLUSTER_COM_SCRIPT = "Vazamento em Sao Paulo </script><img src=x onerror=alert(1)>"


# ---------------------------------------------------------------------------
# Infra: superuser + payloads de changeform
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _armazena_staticfiles_sem_manifest():
    """Renderizar uma pagina do Admin exige `{% static %}` resolver o CSS do
    admin. `config.settings.STORAGES` usa
    `CompressedManifestStaticFilesStorage`, que le um `staticfiles.json`
    produzido por `collectstatic` — arquivo que a suite nao gera. Sem isto,
    qualquer teste que espere a tela de mudanca REAPRESENTADA (HTTP 200)
    toma `ValueError: Missing staticfiles manifest entry for
    'admin/css/base.css'` e vira 500, que e um falso positivo de "o Admin
    esta quebrado".

    So o armazenamento de static e trocado; `STORAGES["default"]` (media de
    upload) fica como esta. Um POST aceito (HTTP 302) nao renderiza template
    e por isso nao era afetado — e por isso que o bug passou despercebido nos
    testes de Admin que existiam.
    """
    from django.test import override_settings

    with override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
            },
        }
    ):
        yield


@pytest.fixture
def admin_client_logado(client, django_user_model):
    """`client` do pytest-django autenticado como superuser — todo POST de
    changeform abaixo e um POST REAL de Admin (session + login), nao uma
    chamada de servico."""
    usuario = django_user_model.objects.create_user(
        email="admin_p101b@exemplo.test",
        nome="Admin P1-01b",
        password="SenhaDeTesteP101b-2026",
        is_staff=True,
        is_superuser=True,
    )
    client.force_login(usuario)
    return client


def _payload_item(**overrides):
    """Payload de `admin:catalogo_noticias_newsitem_add` com TODOS os campos
    do form. Faltar um campo required faz o form reexibir (HTTP 200) e o teste
    passaria por um motivo errado — por isso o dict completo."""
    dados = {
        "titulo": "Titulo de teste",
        "resumo_proprio": "",
        "conteudo_bruto": "",
        "conteudo_completo": "",
        "url_fonte_original": "https://fonte-externa.test/p101b/1",
        "nome_fonte": "Fonte de Teste",
        "categoria": "cidades",
        "autor": "",
        "pais": "",
        "estado": "",
        "cidade": "",
        "imagem_url": "",
        # SplitDateTime: o POST traz os dois slots, mesmo vazios.
        "timestamp_publicacao_fonte_0": "",
        "timestamp_publicacao_fonte_1": "",
        "status_revisao": NewsItem.STATUS_PENDENTE,
        "cluster": "",
        "tags": "[]",
    }
    dados.update(overrides)
    return dados


def _payload_cluster(**overrides):
    """Payload de `admin:catalogo_noticias_newscluster_add`, incluindo o
    formset de gerenciamento do inline `NewsItemInline` — sem ele o POST e
    recusado com HTTP 400 e nada e salvo."""
    dados = {
        "titulo_acontecimento": "Acontecimento de teste",
        "categoria_dominante": "cidades",
        "numero_fontes_distintas": "1",
        "itens-TOTAL_FORMS": "0",
        "itens-INITIAL_FORMS": "0",
        "itens-MIN_NUM_FORMS": "0",
        "itens-MAX_NUM_FORMS": "1000",
    }
    dados.update(overrides)
    return dados


def _mensagens(resposta) -> list[str]:
    """Mensagens do messages framework que o Admin mostra ao operador na tela
    de destino (o redirect do changeform)."""
    return [str(m) for m in get_messages(resposta.wsgi_request)]


def _request_admin(rf, django_user_model, email="operador_p101b@exemplo.test"):
    """`request` de POST de admin, com superuser e um armazenamento de
    mensagens que da para ler depois. Usado nos testes que chamam `save_model`
    direto (o `ModelAdmin` exige `request` e `message_user` exige storage)."""
    from django.contrib.messages.storage.fallback import FallbackStorage

    request = rf.post("/admin/")
    request.user = django_user_model.objects.create_user(
        email=email, nome="Operador P1-01b", is_staff=True, is_superuser=True
    )
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _avisos_de_limite(request) -> list[str]:
    return [str(m) for m in request._messages]


def _ajustes_no_log(caplog) -> list[str]:
    """Ajustes da politica registrados por `catalogo_noticias.limites_admin`
    durante o trecho coberto por `caplog`.

    Preferido a `message_user` quando a medicao precisa ser POR REQUEST: o
    armazenamento de mensagens do Admin vive na sessao e, num POST aceito
    (HTTP 302) em que nenhum template consome a fila, as mensagens NAO sao
    marcadas como usadas — elas se acumulam na sessao e reaparecem na
    resposta seguinte. Ler `get_messages()` de um POST posterior mistura os
    avisos dos POSTs anteriores. O log e por evento e nao tem esse estado.
    """
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "catalogo_noticias.limites_admin"
        and "politica de limites ajustou" in r.getMessage()
    ]


# ---------------------------------------------------------------------------
# 1. O DEFEITO: `</script>` no titulo persistia byte-identico pelo Admin
# ===========================================================================


def test_admin_nao_persiste_script_no_titulo_do_item(admin_client_logado):
    """REGRESSAO do achado do P1-01b.

    Um titulo com `</script>` submetido pelo Admin nao pode chegar ao banco:
    o frontend injeta `NewsItem.titulo` em `<script type="application/ld+json">`
    e, sem escape, o navegador fecha o bloco `ld+json` no `</script>` do
    titulo, trunca o JSON-LD e executa o resto como HTML.

    Antes da correcao o POST devolvia 302 e o banco devolvia o titulo
    byte-identico.
    """
    resposta = admin_client_logado.post(
        reverse("admin:catalogo_noticias_newsitem_add"),
        _payload_item(titulo=TITULO_COM_SCRIPT),
    )
    assert resposta.status_code == 302, (
        f"o titulo com </script> tem de ser aceito e saneado, nao recusado; "
        f"voltou {resposta.status_code}: "
        f"{getattr(resposta, 'context', {}).get('errors') if resposta.status_code == 200 else ''}"
    )

    item = NewsItem.objects.get()
    assert item.titulo != TITULO_COM_SCRIPT, "o titulo nao pode voltar byte-identico"
    assert "</script>" not in item.titulo.lower()
    assert "<script" not in item.titulo.lower()
    assert "<img" not in item.titulo.lower()
    # O conteudo editorial sobreviveu: o que se remove e a marcação, nao o texto.
    assert "Prefeitura anuncia obra" in item.titulo


def test_admin_avisa_que_ajustou_o_titulo(admin_client_logado):
    """O corte/saneamento no Admin e **avisado**, nunca silencioso: e a
    condicao que torna aceitavel truncar aqui em vez de recusar (o operador
    esta vendo e corrigindo — mas so ajuda se ele for informado)."""
    resposta = admin_client_logado.post(
        reverse("admin:catalogo_noticias_newsitem_add"),
        _payload_item(titulo=TITULO_COM_SCRIPT),
    )
    assert resposta.status_code == 302
    avisos = [m for m in _mensagens(resposta) if "politica de limites" in m]
    assert avisos, f"nenhum aviso de ajuste; mensagens={_mensagens(resposta)}"
    assert any("titulo" in m for m in avisos)


def test_admin_nao_persiste_script_no_titulo_do_cluster(admin_client_logado):
    """`NewsClusterAdmin` nao tem `readonly_fields`: `titulo_acontecimento` e
    editavel e o `save_model` nao aplicava a politica. Mesmo defeito, mesmo
    fechamento."""
    resposta = admin_client_logado.post(
        reverse("admin:catalogo_noticias_newscluster_add"),
        _payload_cluster(titulo_acontecimento=CLUSTER_COM_SCRIPT),
    )
    assert resposta.status_code == 302, (
        f"voltou {resposta.status_code}; esperado 302 (aceito e saneado)"
    )

    cluster = NewsCluster.objects.get()
    assert cluster.titulo_acontecimento != CLUSTER_COM_SCRIPT
    assert "</script>" not in cluster.titulo_acontecimento.lower()
    assert "<img" not in cluster.titulo_acontecimento.lower()
    assert "Vazamento em Sao Paulo" in cluster.titulo_acontecimento

    avisos = [m for m in _mensagens(resposta) if "politica de limites" in m]
    assert avisos, "o ajuste do titulo do cluster tambem tem de ser avisado"


# ---------------------------------------------------------------------------
# 2. TITULO ACIMA DO LIMITE: truncado com aviso (e nao recusado)
# ===========================================================================


def test_save_model_trunca_titulo_acima_do_limite_e_avisa(rf, django_user_model):
    """Acima do `varchar(N)`, a politica e TRUNCAR — e avisar.

    Onde o limite e alcancavel e o `save_model` (a ultima porta antes do
    INSERT). O `ModelForm` do Admin tambem rejeita acima do `max_length`
    (medido, e coberto pelo teste 3), mas `save_model` nao chama `full_clean`
    e e o que garante a invariante para QUALQUER chamador da ultima porta —
    action do admin, `form.save()` de um form futuro, teste.

    Este teste chama `save_model` de verdade, com um objeto acima do limite,
    e mede as tres coisas: o que foi gravado, que cabe no teto, e o aviso.
    """
    from django.contrib import admin as dj_admin

    request = _request_admin(rf, django_user_model)
    model_admin = NewsItemAdmin(NewsItem, dj_admin.site)
    item = NewsItem(
        titulo="T" * (LIMITE_TITULO + 120),
        url_fonte_original="https://fonte-externa.test/p101b/truncado",
        nome_fonte="Fonte de Teste",
    )
    model_admin.save_model(request, item, None, False)

    assert len(item.titulo) <= LIMITE_TITULO, "o valor gravado tem de caber no varchar(N)"
    assert item.pk is not None, "o save_model tem de ter gravado"
    guardado = NewsItem.objects.get(pk=item.pk)
    assert len(guardado.titulo) <= LIMITE_TITULO

    avisos = _avisos_de_limite(request)
    assert any("politica de limites" in m and "titulo" in m for m in avisos), (
        f"truncar sem avisar seria corte silencioso; mensagens={avisos}"
    )


def test_aplicar_limites_no_admin_corta_com_elipse():
    """O corte preserva o texto util e marca a elipse (mesma `truncar` da
    ingestao — nenhuma copia deste arquivo)."""
    item = NewsItem(
        titulo="T" * (LIMITE_TITULO + 500),
        url_fonte_original="https://fonte-externa.test/p101b/elipse",
        nome_fonte="Fonte",
    )
    notas = aplicar_limites_no_admin(item)
    assert len(item.titulo) == LIMITE_TITULO
    assert item.titulo.endswith(limites.SUFIXO_ELLIPSIS)
    assert len(notas) == 1 and "'titulo'" in notas[0]


# ---------------------------------------------------------------------------
# 3. `url_fonte_original` ACIMA DO LIMITE: recusado com mensagem clara
# ===========================================================================


def test_admin_recusa_url_acima_do_limite_com_mensagem(admin_client_logado):
    """`url_fonte_original` e a chave de rastreabilidade (BRD secao 18):
    truncar `https://a.test/noticia-de-rio` nao produziria a mesma materia,
    produziria OUTRA. A resposta correta e recusar, com mensagem — nunca truncar
    em silencio.

    E2E: nada e persistido e a tela reapresenta o formulario com o erro.
    """
    url_longa = "https://fonte-externa.test/p101b/" + "segmento/" * 130
    assert len(url_longa) > LIMITE_URL, "a URL do teste tem de passar do limite"

    resposta = admin_client_logado.post(
        reverse("admin:catalogo_noticias_newsitem_add"),
        _payload_item(url_fonte_original=url_longa),
    )
    assert resposta.status_code == 200, "formulario reexibido, nao aceito"
    assert not NewsItem.objects.exists(), "nada pode ter sido persistido"

    contexto = resposta.context
    erros = contexto["adminform"].form.errors
    assert "url_fonte_original" in erros, f"o erro tem de estar no campo; erros={erros}"
    texto = " ".join(erros["url_fonte_original"])
    assert str(LIMITE_URL) in texto, f"a mensagem tem de dizer o limite; texto={texto!r}"


def test_form_do_admin_recusa_url_acima_do_limite_mesmo_sem_max_length_do_campo(admin_client_logado):
    """Prova de que a CHECAGEM DO MIXIN** existe e funciona**, e nao e apenas
    uma linha Morta sob o `max_length` do campo do formulario.

    O `ModelForm` do Admin ja rejeita acima do `max_length` (o teste anterior
    mede isso). Aqui o campo do formulario e construido SEM `max_length` — a
    situacao em que o campo do formulario e mais permissivo que a politica
    (um form customizado futuro, um `formfield_overrides`, um
    `formfield_for_dbfield`). A politica tem de ser a ultima palavra: o erro
    sai com o texto dela,e que tem o mesmo teto da ingestao.
    """
    from django import forms
    from django.forms.models import modelform_factory

    class FormSemMaxLength(LimitesModelFormMixin):
        """O mesmo mixin da politica, mas com o campo da URL construido SEM
        `max_length` — a situacao em que o campo do formulario e mais
        permissivo que a politica do modelo (form customizado futuro,
        `formfield_overrides`, `formfield_for_dbfield`)."""

        class Meta:
            model = NewsItem
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields["url_fonte_original"] = forms.URLField(required=False)

    url_longa = "https://fonte-externa.test/p101b/" + "sem-max/" * 130
    dados = {
        "titulo": "Titulo qualquer",
        "url_fonte_original": url_longa,
        "nome_fonte": "Fonte",
        "status_revisao": NewsItem.STATUS_PENDENTE,
        "tags": "[]",
    }
    form = FormSemMaxLength(data=dict(dados))
    assert form.is_valid() is False
    assert "url_fonte_original" in form.errors
    texto = " ".join(form.errors["url_fonte_original"])
    assert str(LIMITE_URL) in texto, (
        f"a mensagem tem de vir da politica (com o teto do modelo); texto={texto!r}"
    )

    # `modelform_factory` tambem precisa passar: e o caminho que o
    # `ModelAdmin.get_form` usa de verdade.
    form_admin = modelform_factory(NewsItem, form=LimitesModelFormMixin, fields="__all__")(
        data=dict(dados)
    )
    assert form_admin.is_valid() is False
    assert str(LIMITE_URL) in " ".join(form_admin.errors["url_fonte_original"])


def test_save_model_recusa_url_acima_do_limite_com_erro_explicito(rf, django_user_model):
    """A ultima linha de defesa: `save_model` LEVANTA (nao trunca) quando um
    `RECUSAR_ITEM` passa do limite, com a razao no texto da excecao.

    No fluxo do Admin o formulario ja recusou antes (teste 3), entao isto
    cobre o chamador que nao passa pelo formulario — e garante que a
    invariante "identificador nunca truncado" nao dependa do formulario.
    """
    from django.contrib import admin as dj_admin

    request = _request_admin(rf, django_user_model, email="operador2_p101b@exemplo.test")
    model_admin = NewsItemAdmin(NewsItem, dj_admin.site)
    item = NewsItem(
        titulo="Titulo ok",
        url_fonte_original="https://fonte-externa.test/p101b/" + "x" * (LIMITE_URL + 50),
        nome_fonte="Fonte",
    )
    with pytest.raises(CampoForaDoLimiteError) as excinfo:
        model_admin.save_model(request, item, None, False)
    assert excinfo.value.campo == "url_fonte_original"
    assert str(LIMITE_URL) in str(excinfo.value)
    assert not NewsItem.objects.exists(), "nada pode ter sido persistido"


# ---------------------------------------------------------------------------
# 4. A EDICAO LEGITIMA NAO PODE QUEBRAR (idempotencia)
# ===========================================================================


def _item_ja_truncado_ingestao():
    """Simula exatamente o estado que a ingestao deixa: um item cujo titulo ja
    foi truncado com elipse (o valor tem `LIMITE_TITULO` caracteres) e cujo
    `status_revisao` ainda e `pendente`."""
    item = NewsItem(
        titulo="Titulo longo da materia " + "T" * LIMITE_TITULO,
        url_fonte_original="https://fonte-externa.test/p101b/ja-truncado",
        nome_fonte="Fonte de Teste",
    )
    limites.limitar_textos(item)  # a MESMA politica da ingestao
    assert len(item.titulo) == LIMITE_TITULO
    return NewsItem.objects.create(**{campo.name: getattr(item, campo.name) for campo in item._meta.concrete_fields if campo.name != "id"})


def test_editar_so_outro_campo_nao_corrompe_o_titulo(admin_client_logado):
    """O caso que o item 4 do enunciado exige: um operador que muda SO o
    `status_revisao` de uma noticia cujo titulo a ingestao ja truncou nao pode
    ter o titulo re-truncado de forma destrutiva, nem ver erro.

    Sem `truncar` idempotente, um segundo passe empilharia outra elipse e
    comeria mais um caractere do texto a cada edicao da fila.
    """
    item = _item_ja_truncado_ingestao()
    titulo_antes = item.titulo
    assert len(titulo_antes) == LIMITE_TITULO

    resposta = admin_client_logado.post(
        reverse("admin:catalogo_noticias_newsitem_change", args=[item.pk]),
        _payload_item(
            titulo=titulo_antes,
            url_fonte_original=item.url_fonte_original,
            status_revisao=NewsItem.STATUS_APROVADO,
        ),
    )
    assert resposta.status_code == 302, (
        f"a edicao legitima nao pode dar erro; voltou {resposta.status_code}"
    )

    item.refresh_from_db()
    assert item.titulo == titulo_antes, "o titulo foi corrompido por uma edicao de status"
    assert len(item.titulo) == LIMITE_TITULO, "o titulo encolheu (elipse empilhada)"
    assert item.status_revisao == NewsItem.STATUS_APROVADO, "o status nao foi salvo"

    # E sem aviso: nada mudou, entao nao ha o que avisar.
    avisos = [m for m in _mensagens(resposta) if "politica de limites" in m]
    assert not avisos, f"nada mudou, entao nao deveria haver aviso; avisos={avisos}"


def test_truncamento_e_idempotente_ao_salvar_duas_vezes(admin_client_logado, caplog):
    """Salvar o MESMO titulo duas vezes da o MESMO resultado — a propriedade
    que torna a reaplicacao da politica em cada `save_model` segura.

    Mede os dois lados, porque sao situacoes diferentes:

    1. O operador reenvia o valor CRU duas vezes (o navegador re-postou o
       form). As duas gravacoes tem de dar o mesmo resultado, e as duas tem de
       avisar — ele nao esta vendo o valor ja limpo, entao o aviso e honesto.
    2. O operador reenvia o valor JA SANEADO, que e o que acontece quando ele
       abre a tela de mudanca e mexe so em outro campo. A segunda passagem
       nao muda nada e nao avisa: e o teste 4, isolado.

    A medicao por request usa o LOG, nao as mensagens da sessao — ver
    `_ajustes_no_log`.
    """
    url = "https://fonte-externa.test/p101b/idem"
    with caplog.at_level("INFO", logger="catalogo_noticias.limites_admin"):
        primeira = admin_client_logado.post(
            reverse("admin:catalogo_noticias_newsitem_add"),
            _payload_item(titulo=TITULO_COM_SCRIPT, url_fonte_original=url),
        )
        assert primeira.status_code == 302
        item = NewsItem.objects.get(url_fonte_original=url)
        titulo_primeira = item.titulo
        ajustes_1 = _ajustes_no_log(caplog)

        # 2o POST com o MESMO valor cru, na tela de MUDANCA (nao de inclusao).
        caplog.clear()
        segunda = admin_client_logado.post(
            reverse("admin:catalogo_noticias_newsitem_change", args=[item.pk]),
            _payload_item(titulo=TITULO_COM_SCRIPT, url_fonte_original=url),
        )
        assert segunda.status_code == 302
        item.refresh_from_db()
        assert item.titulo == titulo_primeira, (
            f"o 2o save mudou o titulo: {titulo_primeira!r} -> {item.titulo!r}"
        )
        ajustes_2 = _ajustes_no_log(caplog)

        # 3o POST com o valor JA SANEADO — o que o formulario reexibe de fato.
        caplog.clear()
        terceira = admin_client_logado.post(
            reverse("admin:catalogo_noticias_newsitem_change", args=[item.pk]),
            _payload_item(titulo=titulo_primeira, url_fonte_original=url),
        )
        assert terceira.status_code == 302
        item.refresh_from_db()
        assert item.titulo == titulo_primeira, "o titulo encolheu na 3a gravacao"
        ajustes_3 = _ajustes_no_log(caplog)

    # 1 e 2: mesmo valor de entrada, mesmo resultado, aviso nos dois casos.
    assert ajustes_1 and ajustes_2, (
        f"os dois saves com o valor CRU tinham de registrar ajuste: {ajustes_1} / {ajustes_2}"
    )
    # 3: o valor ja estava dentro da politica — nada a ajustar, nada a avisar.
    assert ajustes_3 == [], (
        f"valor ja saneado nao pode gerar ajuste; registro={ajustes_3}"
    )


def test_aplicar_limites_no_admin_e_idempotente():
    """A funcao em si: a 2a chamada nao muda nada e nao devolve nota. E o que
    garante que reaplicar a politica em toda escrita seja seguro, e nao um
    desgaste cumulativo do dado."""
    item = NewsItem(
        titulo=TITULO_COM_SCRIPT,
        url_fonte_original="https://fonte-externa.test/p101b/idem-funcao",
        nome_fonte="Fonte",
    )
    primeira = aplicar_limites_no_admin(item)
    titulo_1 = item.titulo
    segunda = aplicar_limites_no_admin(item)
    assert item.titulo == titulo_1
    assert primeira and not segunda, (
        f"a 2a passagem nao deveria ter nada a fazer: {primeira} / {segunda}"
    )


def test_editar_so_outro_campo_do_cluster_nao_corrompe_o_titulo(admin_client_logado):
    """O mesmo para `NewsCluster.titulo_acontecimento`."""
    cluster = NewsCluster(
        titulo_acontecimento="C" * (LIMITE_TITULO_CLUSTER + 80)
    )
    # A politica ANTES do INSERT: e assim que a ingestao faz, e e o unico jeito
    # de o estado "ja truncado pela ingestao" existir no banco (o Postgres
    # recusaria o valor de 380 caracteres num `varchar(300)`).
    limites.limitar_textos(cluster)
    cluster.save()
    titulo_antes = cluster.titulo_acontecimento
    assert len(titulo_antes) == LIMITE_TITULO_CLUSTER

    resposta = admin_client_logado.post(
        reverse("admin:catalogo_noticias_newscluster_change", args=[cluster.pk]),
        _payload_cluster(
            titulo_acontecimento=titulo_antes,
            categoria_dominante="economia",
            numero_fontes_distintas="1",
        ),
    )
    assert resposta.status_code == 302, (
        f"a edicao legitima do cluster nao pode dar erro; voltou {resposta.status_code}"
    )
    cluster.refresh_from_db()
    assert cluster.titulo_acontecimento == titulo_antes
    assert cluster.categoria_dominante == "economia", "o campo editado nao foi salvo"
    assert not [m for m in _mensagens(resposta) if "politica de limites" in m]


# ---------------------------------------------------------------------------
# 5. A INGESTAO NAO REGRESSOU
# ===========================================================================


def test_ingestao_continua_limpando_limitando_e_recusando(caplog):
    """Nao-regressao do caminho de INGESTAO: o pipeline segue passando pela
    MESMA politica e continua (a) limpando HTML, (b) respeitando o teto e
    (c) recusando URL fora do limite. Se este teste falhar, a correcao do Admin
    quebrou o pipeline — que seria o custo real do item.

    Exercita `executar_ingestao` de verdade, com uma fonte falsa (um
    `ItemBruto` com `<script>` e um com URL de 5000 chars) e um
    `SummarizationProvider` de confianca, e confirma os tres contratos.
    """
    import logging

    from catalogo_noticias.providers.news_source import ItemBruto
    from catalogo_noticias.providers.summarization import (
        ResultadoResumo,
        SummarizationProvider,
    )
    from catalogo_noticias.services.ingestao import executar_ingestao

    class _FonteFalsa:
        nome_fonte = "Fonte Falsa"

        def __init__(self, itens):
            self.itens = itens

        def buscar_itens(self):
            return list(self.itens)

    class _ResumoConfiavel(SummarizationProvider):
        def resumir_e_classificar(self, itens_brutos):
            return ResultadoResumo(
                resumo=f"Resumo proprio de {itens_brutos[0].url_fonte_original}.",
                categoria="cidades",
            )

    fontes = [
        _FonteFalsa(
            [
                ItemBruto(
                    titulo="Titulo com <script>alert(1)</script> malicioso",
                    url_fonte_original="https://fonte-falsa.test/p101b/ok",
                    nome_fonte="Fonte Falsa",
                    conteudo_bruto="Resumo com <b>markup</b>",
                ),
                # URL gigante: recusada, nunca truncada (identificador).
                ItemBruto(
                    titulo="Item com URL gigante",
                    url_fonte_original="https://fonte-falsa.test/p101b/" + "q" * 5000,
                    nome_fonte="Fonte Falsa",
                    conteudo_bruto="Resumo",
                ),
            ]
        )
    ]

    with caplog.at_level(logging.ERROR):
        registro = executar_ingestao(fontes=fontes, summarization_provider=_ResumoConfiavel())

    # (a) e (b): o item valido entra, limpo e dentro do teto.
    assert NewsItem.objects.count() == 1, (
        f"so o item valido entra; entraram={NewsItem.objects.count()}"
    )
    item = NewsItem.objects.get()
    assert "<script" not in item.titulo.lower()
    assert "</script>" not in item.titulo.lower()
    assert len(item.titulo) <= LIMITE_TITULO
    assert "malicioso" in item.titulo, "o texto editorial sobrevive ao saneamento"

    # (c): a URL fora do limite foi recusada, e a falha ficou registrada.
    erros = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    texto = " ".join(erros)
    assert "url_fonte_original" in texto, f"a recusa tem de ser registrada; erros={texto!r}"

    # O `RegistroExecucaoIngestao` tambem tem de carregar o motivo da recusa:
    # `total_itens_ingeridos` conta os itens TENTADOS (2), nao os persistidos
    # (1) — por isso o assert que prova a recusa e `NewsItem.objects.count()`
    # acima, e o `erros_por_fonte`, e nao esse contador.
    assert registro.total_itens_ingeridos == 2, "o placar conta o que foi tentado"
    assert any("url_fonte_original" in motivo for motivo in registro.erros_por_fonte.values()), (
        f"o motivo da recusa tem de ficar no registro; erros={registro.erros_por_fonte}"
    )


def test_ingestao_persiste_item_com_html_malicioso_sem_script():
    """Mesma garantia do ponto de vista do BANCO, pelo caminho da ingestao:
    o que a ingestao grava ja vem limpo, entao reaplicar a politica do Admin
    sobre esse valor nao muda nada (e o que o teste 4 mede)."""
    from catalogo_noticias.services import ingestao as svc

    item = NewsItem(
        titulo="Materia real </script><script>alert(1)</script>",
        url_fonte_original="https://fonte-falsa.test/p101b/persistencia",
        nome_fonte="Fonte",
        conteudo_bruto="<p>bruto com <i>html</i></p>",
    )
    svc._persistir_news_items_em_lote([item])

    guardado = NewsItem.objects.get()
    assert "</script>" not in guardado.titulo.lower()
    assert "<script" not in guardado.titulo.lower()
    assert "Materia real" in guardado.titulo
    assert guardado.conteudo_bruto == "bruto com html"
    # Idempotente: reaplicar a politica do Admin sobre o valor JA saneado pela
    # ingestao nao produz aviso nem altera nada.
    notas = aplicar_limites_no_admin(guardado)
    assert not notas, f"valor ja dentro da politica nao deveria gerar aviso: {notas}"


# ---------------------------------------------------------------------------
# 6. O MIXIN E OPT-IN: nao trava nenhum outro Admin
# ===========================================================================


def test_mixin_ignora_models_fora_da_politica():
    """`comunidade.Publicacao.titulo` tambem e editavel e sem politica (achado
    da varredura), mas este item nao expande escopo. O que importa e que o
    mixin, aplicado por engano a um model fora da politica, nao quebre o
    Admin: devolve lista vazia em vez de explodir."""
    from comunidade.models import Publicacao

    publicacao = Publicacao(titulo="Post da comunidade", conteudo="corpo")
    assert aplicar_limites_no_admin(publicacao) == []
    assert publicacao.titulo == "Post da comunidade"


def test_mapa_do_admin_cobre_exatamente_os_models_da_politica():
    """Trava a intencao do mapa `APLICAR_LIMITES_POR_MODEL`: se um model novo
    entrar na politica (ou um sair), este teste falha e alguem tem de olhar —
    em vez do mixin silenciosamente nao aplicar nada e o Admin ficar aberto de
    novo sem ninguem perceber.

    Cross-check real, nao tautologico: `services/limites.py` declara os campos
    da politica com o import de `NewsItem`/`NewsCluster`, entao o mapa tem de
    apontar para exatamente esses dois models.
    """
    from catalogo_noticias import limites_admin

    assert set(limites_admin.APLICAR_LIMITES_POR_MODEL) == {NewsItem, NewsCluster}
    assert set(limites_admin.APLICAR_LIMITES_POR_MODEL) == {
        limites.NewsItem,
        limites.NewsCluster,
    }


def test_as_duas_admin_do_catalogo_herdam_o_mixin():
    """Os dois `ModelAdmin` que escrevem `NewsItem`/`NewsCluster` de texto
    precisam mesmo estar com o mixin. Sem este teste, da para remover o
    `LimitesAdminMixin` da classe base sem quebrar nada em tempo de import —
    so o defeito volta, em silencio."""
    assert issubclass(NewsItemAdmin, LimitesAdminMixin)
    assert issubclass(NewsClusterAdmin, LimitesAdminMixin)


def test_inline_de_newsitem_e_totalmente_somente_leitura(rf, django_user_model):
    """O `NewsItemInline` de `NewsClusterAdmin` NAO e caminho de escrita de
    `NewsItem` e por isso nao recebe a politica. Este teste trava essa
    premissa: se algum campo dele ficar editavel, o inline passa a escrever
    `NewsItem.titulo` sem passar pela politica e o item quebraria de novo."""
    from django.contrib import admin as dj_admin

    from catalogo_noticias.admin import NewsItemInline

    inline = NewsItemInline(NewsCluster, dj_admin.site)
    form_class = inline.get_formset(_request_admin(rf, django_user_model)).form
    editaveis = [nome for nome, campo in form_class.base_fields.items() if not campo.disabled]
    assert editaveis == [], (
        f"o inline de NewsItem ganhou campos editaveis ({editaveis}); "
        f"se for intencional, ele precisa da politica de limites"
    )
    assert not issubclass(NewsItemInline, LimitesAdminMixin)
