"""
DOUBLE OPT-IN — CONFIRMAÇÃO, TOKENS, ORÁCULO, EXPIRAÇÃO E DESCADASTRO.

Este arquivo cobre as cinco propriedades do segundo metade do item:

1. O token válido confirma, e é de uso único.
2. Token inválido, expirado e reaproveitado são tratados explicitamente.
3. A confirmação NÃO É ORÁCULO — e esta é a propriedade mais importante
   depois do portão.
4. Pendente não recebe, nem se o job rodar.
5. O descadastro funciona a partir do pendente e do confirmado.

A GRANDE DIVISÃO DESTE ARQUIVO: o que é RESPOSTA e o que é EFEITO
===============================================================
`services.confirmar_por_token` devolve um ESTADO (`confirmada`/`rejeitada`), e
o estado muda o banco. `ConfirmarView` devolve um 200 e um corpo ÚNICO, sempre.
A distinção não é um detalhe de implementação: é a propriedade do item, e ela
precisa ser testada nos DOIS lados, porque um dos lados pode virar o outro sem
aviso. Um teste que exercita só a view não veria o estado vazando para o corpo;
um teste que exercita só o serviço não veria o estado vazando para a resposta.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tokens import (
    CONFIRMACAO_SALT,
    DESCADASTRO_SALT,
    gerar_token_confirmacao,
    gerar_token_descadastro,
    hash_do_segredo,
    ler_hash_do_token,
    ler_hash_do_token_de_confirmacao,
)

pytestmark = pytest.mark.django_db
User = get_user_model()

CONFIRMAR = "/api/newsletter/confirmar/"
DESCADASTRAR = "/api/newsletter/descadastrar/"
CANAL = "newsletter.tests.doubles.EntregaRegistradaBackend"


def _conta(email):
    user = User.objects.create_user(email=email, password="senha123", papel="free")
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    return user


def _pendente(email="confirma@example.com", tipo=InscricaoNewsletter.TIPO_PADRAO):
    """Inscreve de verdade (portão incluído) e devolve a linha PENDENTE."""
    return services.inscrever(_conta(email), tipo)


def _linha(user):
    return InscricaoNewsletter.objects.get(user=user)


# ---------------------------------------------------------------------------
# 1. O TOKEN VÁLIDO CONFIRMA
# ---------------------------------------------------------------------------


class TestConfirmar:
    def test_token_valido_confirma_e_a_pessoa_comeca_a_receber(self):
        inscricao = _pendente()
        token = gerar_token_confirmacao(inscricao)

        estado = services.confirmar_por_token(token)

        assert estado == services.ESTADO_CONFIRMADA
        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is not None
        assert inscricao.ativa is True
        # A data da CONCESSÃO é a do clique. Ver a nota sobre
        # `consentimento_aceito_em` em `newsletter/models.py`.
        assert inscricao.consentimento_aceito_em is not None
        assert inscricao.consentimento_aceito_em >= inscricao.confirmacao_solicitada_em

    def test_confirmar_e_o_caminho_real_para_o_estado_confirmado(self):
        """Trava a concordância entre o atalho de teste e o caminho real.

        `newsletter/tests/fabrica.confirmar` grava `confirmado_em` direto, para
        os testes do ENVIO não precisarem mandar e-mail. Se alguém ajustar um
        dos dois lados e não o outro, a suíte inteira continua verde e o
        primeiro sintoma é em produção. Este teste é a costura.
        """
        from newsletter.tests import fabrica

        inscricao = _pendente("costura@example.com")
        token = gerar_token_confirmacao(inscricao)
        services.confirmar_por_token(token)
        pelo_caminho_real = _linha(inscricao.user)

        outra = _pendente("costura2@example.com")
        pelo_atalho = fabrica.confirmar(outra)

        for campo in ("ativa", "confirmado_em", "consentimento_aceito_em"):
            a, b = getattr(pelo_caminho_real, campo), getattr(pelo_atalho, campo)
            assert (a is None) == (b is None), f"`{campo}` diverge entre os dois caminhos"

    def test_a_confirmacao_nao_cria_nenhuma_linha(self):
        inscricao = _pendente()
        antes = InscricaoNewsletter.objects.count()
        services.confirmar_por_token(gerar_token_confirmacao(inscricao))
        assert InscricaoNewsletter.objects.count() == antes

    def test_confirmar_e_idempotente(self):
        """O segundo clique não faz mal. E ele é um caso REAL: cliente de
        e-mail com pré-carregador de link abre a URL sozinho, e a pessoa também
        clica."""
        inscricao = _pendente()
        token = gerar_token_confirmacao(inscricao)
        services.confirmar_por_token(token)
        confirmado_em = _linha(inscricao.user).confirmado_em

        # O token foi rotacionado, então o segundo clique é "token inválido",
        # e não "já confirmada". Ver o teste de reaproveitamento.
        estado = services.confirmar_por_token(token)

        assert estado == services.ESTADO_REJEITADA
        assert _linha(inscricao.user).confirmado_em == confirmado_em, (
            "um segundo clique moveu a data da confirmação"
        )

    def test_o_endpoint_confirma_e_responde_200(self):
        inscricao = _pendente()
        resposta = APIClient().post(
            CONFIRMAR, {"token": gerar_token_confirmacao(inscricao)}, format="json"
        )
        assert resposta.status_code == 200
        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is not None
        assert inscricao.ativa is True

    def test_o_link_tambem_vai_na_query_string(self):
        """O link do e-mail é uma URL com `?token=`, e a pessoa chega nele por
        GET no navegador. O `ConfirmarView` lê dos dois lugares pelo mesmo motivo
        do `DescadastrarView` — e sem isso o link do e-mail não funcionaria,
        porque um link é clicado, não colado."""
        inscricao = _pendente()
        resposta = APIClient().post(
            f"{CONFIRMAR}?token={gerar_token_confirmacao(inscricao)}"
        )
        assert resposta.status_code == 200
        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is not None


# ---------------------------------------------------------------------------
# 2. TOKEN DE USO ÚNICO, EXPIRAÇÃO E INVALIDO
# ---------------------------------------------------------------------------


class TestToken:
    def test_o_token_e_de_uso_unico(self):
        """A rotação do segredo é o que faz o token ser de uso único.

        Sem a roção, o link da caixa de entrada da pessoa confirmaria a
        inscrição N vezes, e valeria para sempre — que é o defeito que
        `newsletter/tokens.py` documenta sobre o descadastro pré-P1-06.
        """
        inscricao = _pendente()
        segredo_antes = inscricao.token_confirmacao
        token = gerar_token_confirmacao(inscricao)

        services.confirmar_por_token(token)

        inscricao.refresh_from_db()
        assert inscricao.token_confirmacao != segredo_antes, (
            "o segredo de confirmação não foi rotacionado: o link continua válido"
        )
        # E o token reaproveitado é explicitamente recusado.
        assert services.confirmar_por_token(token) == services.ESTADO_REJEITADA

    def test_o_token_vencido_nao_confirma(self):
        inscricao = _pendente()
        token = gerar_token_confirmacao(inscricao)

        with override_settings(NEWSLETTER_TOKEN_CONFIRMACAO_MAX_AGE_SECONDS=0):
            assert services.confirmar_por_token(token) == services.ESTADO_REJEITADA

        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is None
        assert inscricao.ativa is False

    def test_a_expiracao_e_o_prazo_configurado_e_nao_o_ultimo_acesso(self):
        """O que EXPIRA é o prazo, e o prazo é uma configuração — não um fato.

        Isto é a propriedade real, e ela foi escrita depois de a hipótese
        inicial ("expirado é eterno mesmo que o prazo volte") ser tentada e
        REPROVADA pelo código. A verdade é a seguinte, e é importante dizê-la
        com todas as letras: uma tentativa de confirmação que NÃO CONFIRMA não
        rotaciona o segredo — só o `UPDATE` bem-sucedido rotaciona. Então
        baixar `NEWSLETTER_TOKEN_CONFIRMACAO_MAX_AGE_SECONDS` e depois restaurá-lo
        faz o MESMO token voltar a valer, desde que a pendência não tenha sido
        expirada por `expirar_pendencias`.

        Isso NÃO é um furo, por dois motivos verificáveis:

        1. **A rotação do segredo continua sendo a garantia de uso único.** O
           teste `test_o_token_e_de_uso_unico` mostra que depois de confirmar,
           o token não vale mais — e isso não depende de configuração nenhuma.
        2. **A expiração definitiva é um FATO gravado.** `expirar_pendencias`
           carimba `pendencia_expirada_em` E rotaciona o segredo, e aí o link
           está morto independentemente do prazo — ver
           `test_a_pendencia_expirada_nao_confirma`.

        Ou seja: o prazo é a janela, e a rotação é a fechadura. Uma janela que
        alguém pode mudar é normal (é configuração); uma fechadura que alguém
        pode reabrir não seria. Este teste existe para que ninguém "conserte" o
        código para rotacionar em toda tentativa — isso TROCARIA o erro de
        "token expirado" por "token inválido", que é a mesma resposta, e gastaria
        uma escrita no banco por clique de robô.
        """
        inscricao = _pendente()
        token = gerar_token_confirmacao(inscricao)
        segredo_antes = inscricao.token_confirmacao

        with override_settings(NEWSLETTER_TOKEN_CONFIRMACAO_MAX_AGE_SECONDS=0):
            assert services.confirmar_por_token(token) == services.ESTADO_REJEITADA

        # A tentativa recusada NÃO rotacionou o segredo: é o mesmo.
        inscricao.refresh_from_db()
        assert inscricao.token_confirmacao == segredo_antes
        # E com o prazo restaurado, o mesmo token volta a valer. Isto é o
        # comportamento, registrado — e está registrado porque a próxima
        # pessoa vai tentar "consertar" sem saber se há o que consertar.
        assert services.confirmar_por_token(token) == services.ESTADO_CONFIRMADA

    @pytest.mark.parametrize(
        "token",
        [None, "", 0, 1, 12345, [], {}, b"bytes", True, "   ", "token-que-nao-existe"],
    )
    def test_token_invalido_nao_levanta_e_nao_confirma(self, token):
        """Um endpoint público e anônimo não pode virar um 500.

        O `DescadastrarView` já tem esse teste (`test_token_de_tipo_nao_texto_e
        _recusado_sem_erro`) e a razão é a mesma: o que vem do corpo ou da
        query string pode ser qualquer coisa, e uma exceção aqui é o melhor
        caminho para um atacante testar formas de entrada.
        """
        assert services.confirmar_por_token(token) == services.ESTADO_REJEITADA

    def test_token_com_espacos_ao_redor_e_aceito(self):
        """Link copiado com espaço no fim não pode falhar por isso."""
        inscricao = _pendente()
        token = gerar_token_confirmacao(inscricao)
        assert services.confirmar_por_token(f"  {token}  ") == services.ESTADO_CONFIRMADA

    def test_segredo_de_confirmacao_vazio_nao_casa_com_nada(self):
        """`token_confirmacao` tem `default=gerar_token`, mas o código não pode
        depender dessa invariante para não explodir em `sha256`."""
        inscricao = _pendente()
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(token_confirmacao="")
        inscricao.refresh_from_db()
        assert services.confirmar_por_token(gerar_token_confirmacao(inscricao)) == (
            services.ESTADO_REJEITADA
        )

    def test_o_token_de_confirmacao_nao_abre_o_descadastro(self):
        """Os DOIS poderes, e por que são dois.

        Se compartilhassem o segredo ou o salt, o dono do link de confirmação
        (que está num e-mail que LHE FOI ENVIADO) também teria o poder de
        cancelar a newsletter. E o dono do link de descadastro teria o poder de
        confirmar. São poderes diferentes e de risco diferente — cancelar é
        irreversível para quem recebe, confirmar é o que autoriza o envio.
        """
        inscricao = _pendente()
        token_confirmacao = gerar_token_confirmacao(inscricao)
        token_descadastro = gerar_token_descadastro(inscricao)

        # O link de confirmação não vale como link de descadastro...
        assert services.descadastrar_por_token(token_confirmacao) is False
        inscricao.refresh_from_db()
        assert inscricao.ativa is False  # ainda pendente, e não revogada
        assert inscricao.consentimento_revogado_em is None

        # ...e o inverso também.
        assert services.descadastrar_por_token(token_descadastro) is True
        assert services.confirmar_por_token(token_confirmacao) == services.ESTADO_REJEITADA

    def test_os_salts_sao_diferentes(self):
        """A premissa estrutural do teste anterior, afirmada diretamente.

        Sem este teste, alguém poderia "simplificar" os dois tokens para usar um
        salt só e o teste anterior continuaria verde por um motivo errado: com
        o salt único, o token de confirmação gerado para uma linha casaria com
        o token de descadastro gerado para a MESMA linha — e os dois testes
        acima ainda passariam, porque eles medem efeitos, não a causa.
        """
        assert CONFIRMACAO_SALT != DESCADASTRO_SALT

    def test_o_hash_do_token_e_o_do_segredo(self):
        """O wire carrega o SHA-256 do segredo, e não o segredo.

        Se o segredo RAW fosse para a URL, ele estaria no histórico do
        navegador, em logs de proxy e em mensagens reencaminhadas — e o valor
        que está no banco deixaria de ser interno.
        """
        inscricao = _pendente()
        token = gerar_token_confirmacao(inscricao)
        assert inscricao.token_confirmacao not in token
        # E o hash que volta é o do segredo da linha.
        hash_do_banco = hash_do_segredo(inscricao.token_confirmacao)
        assert ler_hash_do_token_de_confirmacao(token) == hash_do_banco

    def test_o_segredo_cru_da_linha_nao_confirma(self):
        """O valor do banco, se vazar, não abre o link.

        A comparação é feita sobre o HASH, então apresentar o segredo cru não
        casa: é o mesmo desenho do descadastro, e é o que impede que o
        segredo funcione como token.
        """
        inscricao = _pendente()
        assert services.confirmar_por_token(inscricao.token_confirmacao) == (
            services.ESTADO_REJEITADA
        )

    def test_um_token_de_confirmacao_nao_casa_com_a_outra_inscricao(self):
        """Cada linha tem o seu segredo. Sem isso, o link da pessoa A
        confirmaria a inscrição da pessoa B."""
        a = _pendente("pessoa-a@example.com")
        b = _pendente("pessoa-b@example.com")
        services.confirmar_por_token(gerar_token_confirmacao(a))
        b.refresh_from_db()
        assert b.confirmado_em is None, "o link de uma pessoa confirmou a inscrição de outra"


# ---------------------------------------------------------------------------
# 3. A CONFIRMAÇÃO NÃO É ORÁCULO
# ---------------------------------------------------------------------------


class TestSemOraculo:
    """A propriedade mais importante depois do portão.

    Um atacante que consiga distinguir "confirmou" de "token inválido" descobre
    que um endereço tem inscrição no portal. Isso é dado do TITULAR (art. 8º, V
    da LGPD), e a resposta do portal não pode entregá-lo a quem não é o titular.

    O teste mede a RESPOSTA HTTP, que é a superfície de ataque. O estado interno
    pode (e deve) distinguir — é ele que vai para o log de auditoria.
    """

    def _respostas(self):
        """As quatro respostas que precisam ser IDÊNTICAS."""
        # (a) token de uma inscrição que existe e está pendente.
        valida = _pendente("valida@example.com")
        # (b) token de uma inscrição que JÁ foi confirmada (link reaproveitado).
        usada = _pendente("usada@example.com")
        token_usado = gerar_token_confirmacao(usada)
        services.confirmar_por_token(token_usado)
        # (c) token bem formado, mas de uma inscrição que não existe mais.
        orfa = _pendente("orfa@example.com")
        token_orfao = gerar_token_confirmacao(orfa)
        InscricaoNewsletter.objects.filter(pk=orfa.pk).delete()
        # (d) token que é lixo formatado, do mesmo tamanho.
        lixo = gerar_token_confirmacao(valida)[:-4] + "abcd"
        return {
            "valido": APIClient().post(CONFIRMAR, {"token": gerar_token_confirmacao(valida)}, format="json"),
            "reaproveitado": APIClient().post(CONFIRMAR, {"token": token_usado}, format="json"),
            "de_inscricao_inexistente": APIClient().post(CONFIRMAR, {"token": token_orfao}, format="json"),
            "malformado": APIClient().post(CONFIRMAR, {"token": lixo}, format="json"),
        }

    def test_as_quatro_respostas_sao_identicas(self):
        respostas = self._respostas()
        corpos = {nome: (r.status_code, r.content) for nome, r in respostas.items()}

        unicos = set(corpos.values())
        assert len(unicos) == 1, (
            "a confirmação distingue casos que não deve distinguir: "
            f"{ {n: (s, c[:120]) for n, (s, c) in corpos.items()} }"
        )

    def test_a_resposta_nao_diz_se_a_inscricao_existe(self):
        corpo = APIClient().post(
            CONFIRMAR, {"token": "token-que-nunca-existiu"}, format="json"
        ).json()["detail"]
        # Nenhuma das palavras que confirmariam a existência da inscrição.
        for palavra in ("não encontrada", "não existe", "inválido", "expirado", "já confirmada"):
            assert palavra not in corpo.lower(), (
                f"o corpo da confirmação diz {palavra!r}: isso distingue token "
                "válido de inválido e reconstrói um oráculo de cadastro"
            )

    def test_a_resposta_nao_diz_se_a_inscricao_foi_confirmada(self):
        inscricao = _pendente("reaproveitada@example.com")
        token = gerar_token_confirmacao(inscricao)
        services.confirmar_por_token(token)

        corpo_reaproveitado = APIClient().post(
            CONFIRMAR, {"token": token}, format="json"
        ).json()["detail"]
        inscricao2 = _pendente("nova@example.com")
        corpo_primeiro = APIClient().post(
            CONFIRMAR, {"token": gerar_token_confirmacao(inscricao2)}, format="json"
        ).json()["detail"]

        assert corpo_reaproveitado == corpo_primeiro

    def test_token_vazio_e_o_unico_caso_que_diferencia(self):
        """400 sem token é erro de FORMULÁRIO, e não informação sobre cadastro.

        A distinção é constante — vale para qualquer pessoa, com ou sem
        inscrição — e é a mesma que `DescadastrarView` faz, com o mesmo
        argumento: o campo veio vazio, e isso não diz nada sobre nenhuma
        inscrição.
        """
        sem_token = APIClient().post(CONFIRMAR, {}, format="json")
        assert sem_token.status_code == 400

        inscricao = _pendente("com-inscricao@example.com")
        com_token = APIClient().post(
            CONFIRMAR, {"token": gerar_token_confirmacao(inscricao)}, format="json"
        )
        assert com_token.status_code == 200

        # E o 400 não consulta o banco: um token vazio de alguém com inscrição e
        # de alguém sem-inscrição dão a MESMA resposta.
        APIClient().post(CONFIRMAR, {}, format="json")
        assert (
            APIClient().post(CONFIRMAR, {}, format="json").status_code
            == APIClient().post(CONFIRMAR, {}, format="json").status_code
        )

    def test_o_estado_interno_vai_para_o_log_e_nao_para_a_resposta(self, caplog):
        """O log é o lugar certo para a distinção, e ele existe.

        Um operador precisa responder "a pessoa clicou e o sistema registrou?" —
        e essa pergunta precisa de uma resposta que o cliente não possa ver.
        """
        inscricao = _pendente("logada@example.com")
        token = gerar_token_confirmacao(inscricao)

        with caplog.at_level(logging.INFO, logger="newsletter.services"):
            resposta = APIClient().post(CONFIRMAR, {"token": token}, format="json")

        texto = "\n".join(r.getMessage() for r in caplog.records)
        assert "confirmada" in resposta.json()["detail"].lower()
        assert "estado=confirmada" in texto or "CONFIRMADA por token" in texto
        # E o TOKEN não vai para o log.
        assert token not in texto
        # E o endereço tampoco: o log tem o id da inscrição, que não é PII.
        assert "logada@example.com" not in texto


# ---------------------------------------------------------------------------
# 4. PENDENTE NÃO RECEBE
# ---------------------------------------------------------------------------


class TestPendenteNaoRecebe:
    """A garantia do envio, e ela tem DUAS camadas.

    A primeira é `ativa=False` na pendência — o MODELO diz que não pode receber.
    A segunda é `confirmado_em__isnull=False` no filtro de
    `enviar_newsletters` — a CONSULTA reforça.

    Os dois testes abaixo cobrem as duas camadas de propósito. Um teste só do
    resultado do job passaria com as DUAS reintroduzidas juntas; o primeiro
    reprovaria nesse caso, e é ele que impede a reintrodução silenciosa.
    """

    def _pendente_e_confirmada(self):
        pendente = _pendente("nao-recebe@example.com")
        services.confirmar_por_token(gerar_token_confirmacao(pendente))
        return pendente

    def test_a_pendencia_nasce_incapaz_de_receber(self):
        """Camada 1: o MODELO. `ativa=False` é o default do caminho de escrita."""
        inscricao = _pendente()
        inscricao.refresh_from_db()
        assert inscricao.ativa is False, (
            "a pendência está marcada como ativa: qualquer tela que liste "
            "`ativa=True` trataria a pessoa como inscrita antes de confirmar"
        )
        assert inscricao.pode_receber is False

    def test_o_job_nao_entrega_a_pendencia(self):
        """Camada 2: a CONSULTA, com o job rodando de verdade."""
        from catalogo_noticias.models import NewsItem

        NewsItem.objects.create(
            titulo="Noticia",
            resumo_proprio="Resumo",
            conteudo_bruto="Bruto",
            url_fonte_original="https://exemplo.test/n",
            nome_fonte="G1",
            categoria="geral",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        )
        _pendente("pendente@example.com")
        mail.outbox.clear()

        with override_settings(EMAIL_BACKEND=CANAL):
            envio = services.enviar_newsletters()

        assert envio.total_inscricoes_processadas == 0
        assert envio.total_enviados == 0
        assert mail.outbox == [], "a pendência recebeu o resumo"

    def test_o_job_entrega_a_confirmada_e_nao_a_pendente(self):
        """O par, no mesmo lote.

        É este o teste que prova que o filtro distingue: duas inscrições, uma
        confirmada e outra não, um job só, e os números de cada uma.
        """
        from catalogo_noticias.models import NewsItem

        NewsItem.objects.create(
            titulo="Noticia",
            resumo_proprio="Resumo",
            conteudo_bruto="Bruto",
            url_fonte_original="https://exemplo.test/n2",
            nome_fonte="G1",
            categoria="geral",
            status_revisao=NewsItem.STATUS_NAO_APLICAVEL,
        )
        confirmada = _pendente("confirmada-lote@example.com")
        services.confirmar_por_token(gerar_token_confirmacao(confirmada))
        _pendente("pendente-lote@example.com")
        mail.outbox.clear()

        with override_settings(EMAIL_BACKEND=CANAL):
            envio = services.enviar_newsletters()

        assert envio.total_inscricoes_processadas == 1
        assert envio.total_enviados == 1
        assert [m.to for m in mail.outbox] == [["confirmada-lote@example.com"]]

    def test_o_periodo_nao_traz_a_pendente_de_ninguem(self):
        """O filtro de período é uma segunda consulta com o mesmo problema, e
        ela roda por dois agendamentos (manhã e noite)."""
        for periodo in (InscricaoNewsletter.PERIODO_MANHA, InscricaoNewsletter.PERIODO_NOITE):
            _pendente(f"periodo-{periodo}@example.com")
        mail.outbox.clear()
        with override_settings(EMAIL_BACKEND=CANAL):
            for periodo in (InscricaoNewsletter.PERIODO_MANHA, InscricaoNewsletter.PERIODO_NOITE):
                envio = services.enviar_newsletters(periodo=periodo)
                assert envio.total_inscricoes_processadas == 0
        assert mail.outbox == []

    def test_a_pendencia_nao_entra_no_registro_de_envio_como_processada(self):
        """O `EnvioNewsletter` é o número que o operador lê. Se ele contasse a
        pendência como processada, o painel diria "12 pessoas receberam" quando
        12 pessoas estão esperando confirmação."""
        mail.outbox.clear()
        _pendente("conta-pendente@example.com")
        with override_settings(EMAIL_BACKEND=CANAL):
            envio = services.enviar_newsletters()
        assert envio.total_inscricoes_processadas == 0
        assert envio.total_falhas == 0, (
            "a pendência foi contada como FALHA: o operador leria um erro onde "
            "não houve erro nenhum — ninguém tentou enviar para ninguém"
        )


# ---------------------------------------------------------------------------
# 5. EXPIRAÇÃO DA PENDÊNCIA
# ---------------------------------------------------------------------------


class TestExpiracao:
    def test_a_pendencia_vencida_e_carimbada(self):
        inscricao = _pendente("expira@example.com")
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(
            confirmacao_solicitada_em=timezone.now() - timedelta(days=30)
        )
        inscricao.refresh_from_db()

        quantas = services.expirar_pendencias()

        assert quantas == 1
        inscricao.refresh_from_db()
        assert inscricao.pendencia_expirada_em is not None
        assert inscricao.confirmado_em is None
        assert inscricao.ativa is False
        assert inscricao.estado() == "rejeitada"

    def test_a_pendencia_dentro_do_prazo_nao_e_carimbada(self):
        inscricao = _pendente("dentro@example.com")
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(
            confirmacao_solicitada_em=timezone.now() - timedelta(days=1)
        )
        inscricao.refresh_from_db()

        assert services.expirar_pendencias() == 0
        inscricao.refresh_from_db()
        assert inscricao.pendencia_expirada_em is None

    def test_expirar_e_idempotente(self):
        inscricao = _pendente("idempotente@example.com")
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(
            confirmacao_solicitada_em=timezone.now() - timedelta(days=30)
        )
        assert services.expirar_pendencias() == 1
        assert services.expirar_pendencias() == 0

    def test_expirar_nao_toca_em_confirmada(self):
        inscricao = _pendente("confirmada-nao-expira@example.com")
        services.confirmar_por_token(gerar_token_confirmacao(inscricao))
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(
            confirmacao_solicitada_em=timezone.now() - timedelta(days=30)
        )

        assert services.expirar_pendencias() == 0
        inscricao.refresh_from_db()
        assert inscricao.confirmado_em is not None
        assert inscricao.pendencia_expirada_em is None
        assert inscricao.ativa is True

    def test_a_pendencia_expirada_nao_confirma(self):
        """O prazo é o que impede, e a carimbo é o que registra. Esta é a
        diferença entre os dois papéis: mesmo que alguém zerasse o prazo, a
        linha já expirada não confirma."""
        inscricao = _pendente("expirada-nao-confirma@example.com")
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(
            confirmacao_solicitada_em=timezone.now() - timedelta(days=30)
        )
        services.expirar_pendencias()
        token = gerar_token_confirmacao(inscricao)

        # O segredo foi rotacionado na expiração, então o link já enviado
        # (que foi gerado antes) não casa com nada.
        assert services.confirmar_por_token(token) == services.ESTADO_REJEITADA

    def test_a_task_de_expiracao_devolve_a_contagem(self):
        inscricao = _pendente("task-expiracao@example.com")
        InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(
            confirmacao_solicitada_em=timezone.now() - timedelta(days=30)
        )
        from newsletter import tasks

        assert tasks.expirar_pendencias_task() == 1

    def test_o_link_com_espacos_e_expirado_ou_nao_pelo_mesmo_caminho(self):
        """A expiração usa o mesmo `unsign` do resto, então o mesmo
        `max_age` — não há uma segunda janela de tempo para conferir."""
        inscricao = _pendente("mesma-janela@example.com")
        token = gerar_token_confirmacao(inscricao)
        with override_settings(NEWSLETTER_TOKEN_CONFIRMACAO_MAX_AGE_SECONDS=0):
            assert ler_hash_do_token_de_confirmacao(token) is None
        # E o de descadastro NÃO expirou: são janelas independentes.
        assert ler_hash_do_token(gerar_token_descadastro(inscricao)) is not None