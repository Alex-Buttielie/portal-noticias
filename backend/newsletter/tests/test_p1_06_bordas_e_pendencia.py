"""
P1-06 — BORDAS, CONTEÚDO E PENDÊNCIA JURÍDICA REGISTRADA.

Este arquivo junta três coisas que são pequenas isoladamente mas que precisam
estar escritas em algum lugar explícito:

1. **Bordas de token e de corrida** — as condições em que o cancelamento pode
   dar errado mesmo com a trava certa.
2. **A seleção de conteúdo da newsletter** — as três modalities de inscrição e o
   que cada uma monta no e-mail. Antes do P1-06 esses ramos tinham 0% de
   cobertura (`services.py:46-55` na baseline).
3. **A Pendência jurídica** — escrita como TESTE, e não como comentário, para que
   ela não desapareça quando alguém reformatar o arquivo e para que ninguém
   leia a suíte verde e conclua que o consentimento da newsletter está
   resolvido quando não está.
"""

from __future__ import annotations

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone

from newsletter import services
from newsletter.models import EnvioNewsletter, InscricaoNewsletter
from newsletter.tokens import gerar_token_descadastro, ler_hash_do_token

pytestmark = pytest.mark.django_db
User = get_user_model()

DESCADASTRAR = "/api/newsletter/descadastrar/"


def _consentido(email, papel="free"):
    from django.conf import settings

    user = User.objects.create_user(email=email, password="senha123", papel=papel)
    user.consentimento_aceito_em = timezone.now()
    user.consentimento_versao_termos = settings.TERMOS_VERSAO_ATUAL
    user.save(update_fields=["consentimento_aceito_em", "consentimento_versao_termos"])
    return user


def _noticia(titulo, url, categoria="geral"):
    from catalogo_noticias.models import NewsItem

    return NewsItem.objects.create(
        titulo=titulo,
        resumo_proprio="Resumo",
        conteudo_bruto="Bruto",
        url_fonte_original=url,
        nome_fonte="G1",
        categoria=categoria,
        status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
    )


# ---------------------------------------------------------------------------
# 1. Bordas de token
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valor", [None, 0, 1, 12345, [], {}, b"bytes", True])
def test_token_de_tipo_nao_texto_e_recusado_sem_erro(valor):
    """A view passa o que veio no corpo/querystring, e isso pode não ser texto.
    Um `AttributeError` aqui viraria 500 num endpoint público e anônimo — o
    melhor caminho possível para um atacante testar formas de entrada."""
    assert ler_hash_do_token(valor) is None
    assert services.descadastrar_por_token(valor) is False


def test_token_com_espacos_ao_redor_e_aceito():
    """Link copiado com espaço no fim não pode falhar por isso."""
    inscricao = services.inscrever(
        _consentido("espaco@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    token = gerar_token_descadastro(inscricao)
    assert services.descadastrar_por_token(f"  {token}  ") is True
    inscricao.refresh_from_db()
    assert inscricao.ativa is False


def test_segredo_vazio_nao_casa_com_nada():
    """`token_descadastro` tem `default=gerar_token` e `unique=True`, mas o
    código não deve depender dessa invariante para não explodir em `sha256`."""
    inscricao = services.inscrever(
        _consentido("vazio@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(token_descadastro="")
    inscricao.refresh_from_db()
    assert services.descadastrar_por_token(gerar_token_descadastro(inscricao)) is False


def test_corrida_entre_select_e_update_nao_deixa_a_inscricao_ativa(monkeypatch):
    """Simula a outra requisição que ganhou a corrida.

    `gerar_token()` é avaliado ao montar o `UPDATE`, ou seja, ANTES dele rodar.
    Fazendo o `gerar_token` apagar a linha, o `UPDATE` casa zero registros e o
    código precisa tratar isso como "já foi feito por outro" — e, sobre tudo, não
    pode relançar nem reativar nada.
    """
    inscricao = services.inscrever(
        _consentido("corrida@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    token = gerar_token_descadastro(inscricao)

    def apaga_e_gera():
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).delete()
        return "segredo-novo-que-nao-casa-com-nada"

    monkeypatch.setattr(services, "gerar_token", apaga_e_gera)

    assert services.descadastrar_por_token(token) is False
    assert not InscricaoNewsletter.objects.filter(pk=inscricao.pk).exists()


# ---------------------------------------------------------------------------
# 2. Seleção de conteúdo — as três modalidades de inscrição
# ---------------------------------------------------------------------------


def test_modalidade_padrao_traz_o_resumo_geral():
    _noticia("Geral A", "https://exemplo.test/geral-a")
    _noticia("Esportes B", "https://exemplo.test/esportes-b", categoria="esportes")
    inscricao = services.inscrever(
        _consentido("conteudo-padrao@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    corpo = services.montar_corpo_email(inscricao)
    assert "Geral A" in corpo
    # A fonte original de cada item é obrigatória (critério de aceite 3).
    assert "https://exemplo.test/geral-a" in corpo


def test_modalidade_categoria_filtra_pelas_editorias_escolhidas():
    _noticia("Esportes B", "https://exemplo.test/esportes-b", categoria="esportes")
    inscricao = services.inscrever(
        _consentido("conteudo-categoria@example.com"),
        InscricaoNewsletter.TIPO_CATEGORIA,
        categorias=["esportes"],
    )
    corpo = services.montar_corpo_email(inscricao)
    assert "Esportes B" in corpo
    assert "Geral A" not in corpo


def test_modalidade_categoria_sem_categorias_cai_para_o_resumo_geral():
    _noticia("Geral A", "https://exemplo.test/geral-a")
    inscricao = services.inscrever(
        _consentido("conteudo-categoria-vazia@example.com"),
        InscricaoNewsletter.TIPO_CATEGORIA,
        categorias=[],
    )
    assert "Geral A" in services.montar_corpo_email(inscricao)


def test_modalidade_personalizada_usa_os_interesses_do_usuario():
    _noticia("Esportes B", "https://exemplo.test/esportes-b", categoria="esportes")
    user = _consentido("conteudo-personalizado@example.com", papel="premium")
    user.interesses = ["esportes"]
    user.save(update_fields=["interesses"])

    inscricao = services.inscrever(user, InscricaoNewsletter.TIPO_PERSONALIZADA)
    corpo = services.montar_corpo_email(inscricao)
    assert "Esportes B" in corpo


def test_modalidade_personalizada_sem_interesse_cai_para_o_resumo_geral():
    _noticia("Geral A", "https://exemplo.test/geral-a")
    inscricao = services.inscrever(
        _consentido("personalizado-sem-interesse@example.com", papel="premium"),
        InscricaoNewsletter.TIPO_PERSONALIZADA,
    )
    assert "Geral A" in services.montar_corpo_email(inscricao)


def test_categorias_repetidas_nao_duplicam_itens_no_e_mail():
    _noticia("Esportes B", "https://exemplo.test/esportes-b", categoria="esportes")
    inscricao = services.inscrever(
        _consentido("repetida@example.com"),
        InscricaoNewsletter.TIPO_CATEGORIA,
        categorias=["esportes", "esportes"],
    )
    corpo = services.montar_corpo_email(inscricao)
    assert corpo.count("Esportes B") == 1


# ---------------------------------------------------------------------------
# 3. Modelos e admin
# ---------------------------------------------------------------------------


def test_representacao_textual_da_inscricao_nao_tem_e_mail():
    inscricao = services.inscrever(
        _consentido("repr@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    assert "repr@example.com" not in str(inscricao)
    assert str(inscricao) == f"Newsletter de {inscricao.user_id} (padrao, ativa)"


def test_representacao_textual_do_envio():
    envio = EnvioNewsletter.objects.create(
        total_inscricoes_processadas=3, total_enviados=2, total_falhas=1
    )
    assert "2 enviados" in str(envio)


def test_envio_registro_e_somente_leitura_no_admin():
    """`EnvioNewsletter` é log de execução: o admin não pode criar linha na mão,
    senão o registro de auditoria do envio deixa de significar nada."""
    model_admin = admin.site._registry[EnvioNewsletter]
    assert model_admin.has_add_permission(None) is False


def test_admin_de_inscricao_nao_expoe_o_token_descadastro():
    """O segredo do banco não pode estar na listagem do admin — ele aparece no
    `change` de quem abrir a linha, e o admin é lido por mais gente que o
    necessário."""
    model_admin = admin.site._registry[InscricaoNewsletter]
    assert "token_descadastro" not in model_admin.list_display
    assert "token_descadastro" not in model_admin.list_filter


# ---------------------------------------------------------------------------
# 4. PENDÊNCIA JURÍDICA — escrita como teste, para não ser esquecida
# ---------------------------------------------------------------------------


def test_pendencia_juridica_consentimento_da_newsletter_nao_tem_registro_proprio():
    """NÃO É UM TESTE QUE DEVE PASSAR POR MERITO — é o registro do que falta.

    Ele passa hoje porque o que ele afirma é a **ausência** do registro. Se
    alguém algum dia criar a coluna, este teste quebra de propósito, e a quebra
    é o sinal de que a Pendência foi resolvida e a documentação
    (`newsletter/tokens.py`, docstring de `newsletter/services.py`, relatório do
    P1-06) precisa ser atualizada junto.

    O QUE FALTA
    -----------
    A LGPD distingue finalidades. O consentimento que hoje autoriza o envio da
    newsletter é `User.consentimento_aceito_em` / `consentimento_versao_termos`,
    gravados no **cadastro**, para os **Termos**. Receber newsletter é outra
    finalidade, e o que existe hoje é:

    1. nenhuma data de consentimento *da newsletter* (a que se tem é a do
       aceite dos Termos no cadastro);
    2. nenhuma data de *revogação* — só `ativa=False` e `atualizado_em`, que é
       proxy e se perde se a inscrição for reescrita depois;
    3. nenhuma versão do texto de consentimento específico da newsletter;
    4. nenhuma double opt-in (a inscrição é imediata, no mesmo POST).

    Fechar 1–3 exige migration em `newsletter/models.py` (ex.:
    `consentimento_aceito_em`, `consentimento_revogado_em`,
    `versao_consentimento`), e este item **não pode** criar migration.
    """
    campos = {f.name for f in InscricaoNewsletter._meta.get_fields()}
    assert "consentimento_aceito_em" not in campos, (
        "a Pendência jurídica do P1-06 foi resolvida: atualize a docstring de "
        "newsletter/services.py, o docstring de newsletter/tokens.py e o "
        "relatório do item antes de remover esta asserção"
    )
    assert "consentimento_revogado_em" not in campos
    assert "versao_consentimento" not in campos

    # O que existe em lugar disso, e é o que sustenta a revogação hoje:
    assert "ativa" in campos
    assert "criado_em" in campos
    assert "atualizado_em" in campos
