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
from newsletter.tests.fabrica import inscricao_confirmada_para

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
    inscricao = inscricao_confirmada_para(
        _consentido("espaco@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    token = gerar_token_descadastro(inscricao)
    assert services.descadastrar_por_token(f"  {token}  ") is True
    inscricao.refresh_from_db()
    assert inscricao.ativa is False


def test_segredo_vazio_nao_casa_com_nada():
    """`token_descadastro` tem `default=gerar_token` e `unique=True`, mas o
    código não deve depender dessa invariante para não explodir em `sha256`."""
    inscricao = inscricao_confirmada_para(
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
    inscricao = inscricao_confirmada_para(
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
    inscricao = inscricao_confirmada_para(
        _consentido("conteudo-padrao@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    corpo = services.montar_corpo_email(inscricao)
    assert "Geral A" in corpo
    # A fonte original de cada item é obrigatória (critério de aceite 3).
    assert "https://exemplo.test/geral-a" in corpo


def test_modalidade_categoria_filtra_pelas_editorias_escolhidas():
    _noticia("Esportes B", "https://exemplo.test/esportes-b", categoria="esportes")
    inscricao = inscricao_confirmada_para(
        _consentido("conteudo-categoria@example.com"),
        InscricaoNewsletter.TIPO_CATEGORIA,
        categorias=["esportes"],
    )
    corpo = services.montar_corpo_email(inscricao)
    assert "Esportes B" in corpo
    assert "Geral A" not in corpo


def test_modalidade_categoria_sem_categorias_cai_para_o_resumo_geral():
    _noticia("Geral A", "https://exemplo.test/geral-a")
    inscricao = inscricao_confirmada_para(
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

    inscricao = inscricao_confirmada_para(user, InscricaoNewsletter.TIPO_PERSONALIZADA)
    corpo = services.montar_corpo_email(inscricao)
    assert "Esportes B" in corpo


def test_modalidade_personalizada_sem_interesse_cai_para_o_resumo_geral():
    _noticia("Geral A", "https://exemplo.test/geral-a")
    inscricao = inscricao_confirmada_para(
        _consentido("personalizado-sem-interesse@example.com", papel="premium"),
        InscricaoNewsletter.TIPO_PERSONALIZADA,
    )
    assert "Geral A" in services.montar_corpo_email(inscricao)


def test_categorias_repetidas_nao_duplicam_itens_no_e_mail():
    _noticia("Esportes B", "https://exemplo.test/esportes-b", categoria="esportes")
    inscricao = inscricao_confirmada_para(
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
    """O `__str__` mudou de `ativa` para o ESTADO, e a propriedade continua.

    `estado()` devolve uma das três strings de um vocabulário fechado
    (`newsletter/models.py`), nenhuma delas derivada do titular. Este teste
    trava essa invariante: o `__str__` é o que aparece no admin, no Django
    Admin e em qualquer `print` — e é a superfície mais visível da linha.
    """
    inscricao = inscricao_confirmada_para(
        _consentido("repr@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    assert "repr@example.com" not in str(inscricao)
    assert str(inscricao) == f"Newsletter de {inscricao.user_id} (padrao, confirmada)"
    # E o vocabulário é mesmo fechado: as três strings que `estado()` pode
    # devolver, e nenhuma delas contém nada do titular.
    assert inscricao.estado() in {"pendente", "confirmada", "rejeitada"}


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
# ESTE BLOCO JÁ FOI REFORMULADO UMA VEZ, e a história dele é o registro
# ========================================================================
# A primeira versão se chamava
# `test_pendencia_juridica_consentimento_da_newsletter_nao_tem_registro_proprio`
# e afirmava que as colunas de consentimento NÃO existiam. Ele passava por
# mérito porque afirmava uma ausência, e a convenção era: se alguém criasse as
# colunas, ele quebraria de propósito, e a quebra seria o aviso de que a
# Pendência foi resolvida e a documentação precisa acompanhar.
#
# A colunas existem agora (migration `newsletter/0003_retencao_consentimento_e
# _anonimizacao.py`), então essa convenção se inverteu: o teste passa por
#mérito, e passa porque AFFIRMA QUE A COISA ESTÁ FEITA. Ele é o que impede a
# retenção de regredir — e a assimetria é proposital: um teste que afirma a
# ausência só diz que ninguém agiu; um que afirma a presença diz que a ação
# continua feita.
#
# O item 4 (double opt-in) continua aberto e, por isso, ganhou um teste
# próprio, com a convenção antiga — porque ainda é verdade que a pendência
# está de pé.


def test_registro_datado_do_consentimento_existe_e_e_preenchido():
    """
    AS TRÊS COISAS QUE IMPORTAM, e as três são de primeira classe.

    1. **Data de concessão.** `User.consentimento_aceito_em` data o aceite dos
       TERMOS no cadastro, que é outra finalidade (a LGPD distingue
       finalidades). Quem consentiu em receber newsletter tem que ter um
       registro próprio, datado.
    2. **Data de revogação.** Antes só havia `ativa=False` e `atualizado_em`
       (auto_now) como PROXY — e proxy se perde: qualquer reescrita posterior da
       inscrição move a data, e o momento da revogação deixa de existir. Um
       titular que pergunta "quando cancelei?" não pode receber uma resposta
       que muda com a próxima escrita na linha.
    3. **O e-mail não é recuperável depois do descadastro.** Este é o ponto que
       a instrução original do item supunha existir e não existia: a tabela da
       newsletter NUNCA guardou o endereço. O que guardava era o vínculo com
       `identidade.User`, onde `email` é o `USERNAME_FIELD`. Anonimizar, aqui,
       é cortar esse vínculo.
    """
    campos = {f.name for f in InscricaoNewsletter._meta.get_fields()}

    assert "consentimento_aceito_em" in campos
    assert "consentimento_revogado_em" in campos
    assert "anonimizado_em" in campos
    assert "referencia_opaca" in campos

    inscricao = inscricao_confirmada_para(
        _consentido("datas@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    # A concessão é gravada no ato da inscrição, e não é o aceite dos Termos.
    assert inscricao.consentimento_aceito_em is not None
    # `timezone.now()` é avaliado no Python antes do INSERT, então a concessão
    # é de microsegundos anterior a `criado_em`. O que importa é que as duas
    # dizem a mesma coisa: "agora".
    assert abs(inscricao.consentimento_aceito_em - inscricao.criado_em).total_seconds() < 5
    assert inscricao.consentimento_revogado_em is None
    assert inscricao.anonimizado_em is None

    services.descadastrar_por_token(gerar_token_descadastro(inscricao))

    inscricao.refresh_from_db()
    # A revogação é datada, e é uma data de primeira classe: sobrevive a
    # qualquer reescrita posterior da linha.
    assert inscricao.consentimento_revogado_em is not None
    # E a concessão NÃO some: as duas datas convivem, que é o que prova que
    # houve consentimento E que ele acabou.
    assert inscricao.consentimento_aceito_em is not None
    assert inscricao.consentimento_aceito_em < inscricao.consentimento_revogado_em
    assert inscricao.anonimizado_em is not None


def test_a_data_da_revogacao_sobrevive_a_uma_reescrita_da_linha():
    """
    O motivo de `consentimento_revogado_em` existir, e o que `atualizado_em`
    (auto_now) **não** garantia.

    Este teste encontrou uma afirmação FALSA que estava na documentação do
    projeto. `newsletter/tokens.py` e a docstring de `descadastrar_por_token`
    afirmavam que `atualizado_em` (auto_now) recebia "o instante da revogação".
    NÃO recebia: o descadastro é feito com `QuerySet.update()`, e `auto_now` é
    aplicado por `Model.save()`, não por update de queryset
    (`django/db/models/fields/__init__.py` — `DateTimeField.pre_save` só é
    chamado no caminho do `save()`). Medido nesta suíte: o valor de
    `atualizado_em` é byte a byte o mesmo antes e depois do descadastro.

    Ou seja: **antes deste item não existia data de revogação nenhuma** — nem
    de primeira classe, nem como proxy. Um titular que perguntasse "quando
    cancelei?" não tinha resposta, e a documentação dizia que tinha.
    """
    inscricao = inscricao_confirmada_para(
        _consentido("proxy@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    antes_do_descadastro = inscricao.atualizado_em
    services.descadastrar_por_token(gerar_token_descadastro(inscricao))
    inscricao.refresh_from_db()
    revogada_em = inscricao.consentimento_revogado_em

    # O que a documentação antiga afirmava, e o que é falso.
    assert inscricao.atualizado_em == antes_do_descadastro, (
        "`auto_now` passou a ser aplicado por `QuerySet.update()`; se este teste "
        "quebrar, `atualizado_em` voltou a ser um proxy utilizável e "
        "`consentimento_revogado_em` pode ser reavaliado"
    )
    assert revogada_em is not None, "a data da revogação precisa existir em algum lugar"
    assert revogada_em > antes_do_descadastro, (
        "e precisa estar depois da inscrição — é o único lugar onde ela existe"
    )

    # Reescreve a linha depois. A data da revogação não pode se mover.
    InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(categorias=["geral"])
    inscricao.refresh_from_db()

    assert inscricao.consentimento_revogado_em == revogada_em, (
        "a data da revogação mudou por causa de uma escrita que não foi revogação"
    )


def test_o_vinculo_com_a_pessoa_e_cortado_nos_dois_caminhos_de_revogacao():
    """
    O `DELETE` autenticado e o descadastro pelo link são o MESMO ato jurídico
    (art. 8º, V). Se só um deles cortasse o vínculo, existiria um caminho para
    revogar o consentimento mantendo o endereço linkedado — e um caminho é
    exatamente o que uma anonimização não pode ter.
    """
    por_token = inscricao_confirmada_para(
        _consentido("token@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    services.descadastrar_por_token(gerar_token_descadastro(por_token))
    por_token.refresh_from_db()
    assert por_token.user_id is None, "descadastro por token não cortou o vínculo"

    por_endpoint = inscricao_confirmada_para(
        _consentido("endpoint@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )
    services.cancelar_inscricao(por_endpoint.user)
    por_endpoint.refresh_from_db()
    assert por_endpoint.user_id is None, "cancelamento autenticado não cortou o vínculo"


def test_versao_do_texto_de_consentimento_da_newsletter_continua_pendente():
    """
    NÃO É UM TESTE QUE DEVE PASSAR POR MERITO — é o registro do que ainda
    falta. Passa porque afirma a AUSÊNCIA de uma decisão, e quebra de propósito
    no dia em que a decisão for tomada e gravada.

    A coluna `versao_consentimento` JÁ EXISTE (migration 0003) e é gravada a
    partir de `NEWSLETTER_VERSAO_CONSENTIMENTO` — que tem default VAZIO de
    propósito. Por quê?

    * ainda não existe um texto de consentimento PRÓPRIO da newsletter;
    * `User.consentimento_versao_termos` data o aceite dos **Termos** no
      cadastro, que é outra finalidade, e gravá-lo aqui afirmaria que a pessoa
      leu e aceitou um texto de newsletter que não existe;
    * escrever "1.0" à mão seria **fabricar um artefato jurídico** — a pior
      forma de fechar uma pendência jurídica.

    Quando o texto existir e for publicado, o caminho é: definir
    `NEWSLETTER_VERSAO_CONSENTIMENTO` no ambiente e quebrar este teste de
    propósito, junto com a atualização desta docstring.

    O que continua pendente além deste item: **double opt-in**. A inscrição é
    imediata, no mesmo POST — mudar isso é mudança de fluxo e de produto, não
    de retenção, e por isso não é coberto por teste aqui.
    """
    inscricao = inscricao_confirmada_para(
        _consentido("versao@example.com"), InscricaoNewsletter.TIPO_PADRAO
    )

    from django.conf import settings

    assert not settings.NEWSLETTER_VERSAO_CONSENTIMENTO, (
        "NEWSLETTER_VERSAO_CONSENTIMENTO foi definida: existe agora um texto de "
        "consentimento da newsletter versionado. Atualize esta docstring, a de "
        "`newsletter/services.py` e a de `config/settings.py` antes de remover "
        "esta asserção."
    )
    assert inscricao.versao_consentimento == "", (
        "a versão do consentimento foi gravada sem que exista um texto "
        "correspondente — isso é fabricar um registro jurídico"
    )
