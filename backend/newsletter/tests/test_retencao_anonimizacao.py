"""RETENÇÃO DE DADOS APÓS O DESCADASTRO DA NEWSLETTER.

A SITUAÇÃO MEDIDA, ANTES DESTE ITEM
===================================
`descadastrar_por_token` fazia `UPDATE ... SET ativa=False,
token_descadastro=<novo>`. O token girava (SHA-256 assinado, uso único, 30
dias) e a LINHA PERMANECIA, ligada a `identidade.User` — de onde
`newsletter/services.py` lia `inscricao.user.email` para enviar. Nenhuma data
de revogação existia (ver `test_a_data_da_revogacao_sobrevive_a_uma_reescrita_
da_linha`, que encontrou isso).

A PREMISSA ERRADA DA INSTRUÇÃO ORIGINAL
=======================================
O item pedia para "anonimizar o endereço, substituindo por um hash
determinístico com sal ou por um identificador opaco".

A tabela da newsletter **nunca guardou o endereço de e-mail**. Ela guardava um
VÍNCULO com `identidade.User`, onde `email` é `unique=True` e é o
`USERNAME_FIELD` (`identidade/models.py:36,86`). Não havia "endereço a
anonimizar" aqui — havia uma seta apontando para ele. Por isso a solução é
CORTAR A SETA, e não trocar uma string por outra.

E o hash determinístico com sal foi **descartado**, pela razão que a própria
instrução apontava: e-mail não é segredo de alta entropia, o espaço é
enumerável, e quem tem a linha e o sal (que moram lado a lado) testa candidatos
e confere. Isso é pseudonimização. O que substitui o vínculo é um
identificador ALEATÓRIO (`referencia_opaca`), que não carrega informação
nenhuma sobre o endereço.

O QUE ESTE ARQUIVO PROVA
=======================
| teste                                                       | o que mata                                    |
|-------------------------------------------------------------|-----------------------------------------------|
| o vínculo é NULL e `inscricao.user` é None                   | a recuperabilidade por um JOIN                |
| nenhum campo da linha contém o endereço                       | o dado esquecido em outra coluna              |
| nenhum caminho do código chega ao endereço a partir da linha  | a garantia, e não só o estado do banco         |
| as datas de concessão e revogação continuam                  | destruir a prova junto com o dado             |
| a concessão e a revogação convivem na mesma linha            | "revogado" apagar a existência do consentimento|
| os DOIS caminhos de revogação anonimizam                      | o bypass pelo outro endpoint                  |
| a conta continua existindo — e isso é uma decisão declarada   | a leitura de "o e-mail sumiu do portal"        |
| a linha não some e continua sendo prova                       | resolver LGPD apagando o registro             |
| a referência opaca não é derivada do endereço                 | pseudonimização disfarçada                    |

⚠️ A MIGRATION DESTE ITEM ESTÁ ESCRITA E NÃO APLICADA
=====================================================
`newsletter/migrations/0003_retencao_consentimento_e_anonimizacao.py`. Ela é
versionada e precisa de autorização explícita antes de ser aplicada em qualquer
banco que não seja o efêmero de teste que o `pytest-django` cria e destrói a
cada sessão. Os testes deste arquivo rodam porque a base de teste é construída
a partir dela — o que **não** é o mesmo que aplicá-la em um banco que importa.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from django.test import override_settings

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tokens import gerar_token_descadastro, ler_hash_do_token
from newsletter.tests.fabrica import inscricao_confirmada_para

pytestmark = pytest.mark.django_db
User = get_user_model()

ENDERECO = "titular-que-revogou@example.com"


def _inscrito(email=ENDERECO):
    user = User.objects.create_user(email=email, password="senha123", papel="free")
    user.consentimento_aceito_em = _agora()
    user.save(update_fields=["consentimento_aceito_em"])
    return user, inscricao_confirmada_para(user, InscricaoNewsletter.TIPO_PADRAO)


def _agora():
    from django.utils import timezone

    return timezone.now()


def _revogar(inscricao):
    services.descadastrar_por_token(gerar_token_descadastro(inscricao))
    inscricao.refresh_from_db()
    return inscricao


# ---------------------------------------------------------------------------
# 1. O vínculo é cortado
# ---------------------------------------------------------------------------


class TestOVinculoComAPessoaECortado:

    def test_o_vinculo_vira_null_e_o_acesso_direto_falha(self):
        _, inscricao = _inscrito()
        _revogar(inscricao)

        assert inscricao.user_id is None
        # `user` é NULL, e não "um usuário que não existe": o Django devolve
        # `None` para um `OneToOneField` reverso anulável. A tentativa de
        # chegar ao endereço por aí estoura — e o tipo da exceção é o que
        # impede que um `getattr(..., default)` a transforme num silêncio.
        assert inscricao.user is None
        with pytest.raises(AttributeError):
            inscricao.user.email  # noqa: B018 — a exceção É a asserção

    def test_a_linha_continua_no_banco(self):
        """
        O contraponto obrigatório, e ele é o ponto inteiro do item.

        Destruir a linha resolveria o "problema" apagando a prova de que o
        consentimento existiu e foi revogado — que é o erro OPOSTO. Sob LGPD,
        minimizar é retirar o dado pessoal; não é apagar o registro do ato.
        """
        _, inscricao = _inscrito()
        _revogar(inscricao)

        assert InscricaoNewsletter.objects.filter(pk=inscricao.pk).exists()
        assert InscricaoNewsletter.objects.count() == 1

    def test_nenhuma_consulta_por_usuario_encontra_mais(self):
        _, inscricao = _inscrito()
        user = inscricao.user
        _revogar(inscricao)

        assert not InscricaoNewsletter.objects.filter(user=user).exists()
        assert not InscricaoNewsletter.objects.filter(user_id=user.pk).exists()

    def test_a_linha_anonimizada_nao_e_encontrada_pelo_token_dela(self):
        """
        Um registro de consentimento revogado é prova, não é canal de nada.

        O token foi rotacionado no mesmo `UPDATE`, então o link antigo não
       _matches — e mesmo que casasse, o efeito do `UPDATE` seria neutro numa
        linha já revogada e já sem vínculo. Aqui está o efeito observável: a
        revogação é idempotente do ponto de vista de quem tem a linha.
        """
        _, inscricao = _inscrito()
        token = gerar_token_descadastro(inscricao)
        _revogar(inscricao)

        assert services.descadastrar_por_token(token) is False, (
            "o token de um registro já revogado não pode revogar de novo"
        )
        inscricao.refresh_from_db()
        assert inscricao.ativa is False
        assert inscricao.user_id is None


# ---------------------------------------------------------------------------
# 2. O e-mail não é recuperável por NENHUM caminho do código
# ---------------------------------------------------------------------------


class TestOEnderecoNaoERecuperavel:

    def test_nenhum_campo_da_linha_contem_o_endereco(self):
        """Nem a coluna nova, nem uma que ninguém pensou em limpar."""
        _, inscricao = _inscrito()
        _revogar(inscricao)

        for campo in InscricaoNewsletter._meta.concrete_fields:
            valor = getattr(inscricao, campo.attname)
            assert ENDERECO not in str(valor), f"o campo {campo.name} carrega o endereço"
            assert "@" not in str(valor), f"o campo {campo.name} parece conter um endereço"

    def test_a_referencia_opaca_nao_e_derivada_do_endereco(self):
        """
        A garantia de que não houve pseudonimização disfarçada.

        Um hash determinístico com sal passaria num teste que só olha "o
        endereço sumiu da linha". Ele falharia neste: a referência é
        ALEATÓRIA, então não é função do endereço, e duas inscrições do mesmo
        endereço em linhas diferentes não produzem a mesma referência.
        """
        _, inscricao = _inscrito()
        _revogar(inscricao)

        import hashlib

        candidatos = {
            hashlib.sha256(ENDERECO.encode()).hexdigest(),
            hashlib.md5(ENDERECO.encode()).hexdigest(),  # noqa: S324 — é contra-exemplo
        }
        assert inscricao.referencia_opaca not in candidatos
        assert ENDERECO not in inscricao.referencia_opaca
        assert len(inscricao.referencia_opaca) >= 20

    def test_a_representacao_textual_nao_tem_endereco(self):
        _, inscricao = _inscrito()
        _revogar(inscricao)

        assert ENDERECO not in str(inscricao)
        # E o rótulo deixa explícito que a linha é de uma pessoa que não está
        # mais ali — em vez de mostrar "None" como se fosse um dado faltando.
        assert "anonimizada" in str(inscricao)

    def test_o_log_de_revogacao_nao_carrega_o_endereco_nem_o_user_id(self, caplog):
        """
        O caminho mais óbvio de vazar um dado que se acabou de remover é o log.

        A linha de revogação é escrita no mesmo instante da anonimização, e é
        o único lugar onde o `user_id` ainda estaria ao alcance. Ela não leva
        nenhum dos dois.
        """
        import logging

        _, inscricao = _inscrito()
        with caplog.at_level(logging.INFO, logger="newsletter.services"):
            _revogar(inscricao)

        assert "revogado" in caplog.text
        assert ENDERECO not in caplog.text
        assert str(inscricao.user_id) not in caplog.text or inscricao.user_id is None
        assert "vinculo_com_pessoa_cortado=True" in caplog.text

    def test_nenhum_caminho_de_codigo_parte_da_linha_para_o_endereco(self):
        """
        A garantia, e não o estado do banco.

        Varre os módulos de produção que IMPORTAM o modelo da newsletter — ou
        seja, os que poderiam alcançar um endereço a partir de uma inscrição —
        e afirma que nenhum deles lê `…user.email` a partir do objeto. A
        diferença entre os dois é a que importa: um teste que olha a linha
        prova o que ESTÁ no banco; este prova o que o CÓDIGO FAZ, inclusive
        quando alguém acrescentar uma consulta nova.

        `identidade/views.py` também lê `user.email` (login social), e não é
        infração: ele não conhece `InscricaoNewsletter`, então não sai da
        linha de consentimento — ele sai da conta, que é o outro registro.
        """
        import ast
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        infracoes = []
        for caminho in sorted(raiz.rglob("*.py")):
            partes = set(caminho.relative_to(raiz).parts)
            if partes & {"tests", "migrations", "__pycache__"}:
                continue
            arvore = ast.parse(caminho.read_text(encoding="utf-8-sig"))
            # "Conhece o modelo" é o símbolo aparecer, e não a forma do
            # import: `newsletter/services.py` o importa por caminho RELATIVO
            # (`from .models import InscricaoNewsletter`), e um teste que
            # casasse com `startswith("newsletter")` passaria ao lado do
            # próprio módulo que deveria estar vigiando.
            conhece_a_inscricao = any(
                (isinstance(no, ast.Name) and no.id == "InscricaoNewsletter")
                or (isinstance(no, ast.Attribute) and no.attr == "InscricaoNewsletter")
                for no in ast.walk(arvore)
            )
            if not conhece_a_inscricao:
                continue
            for no in ast.walk(arvore):
                if not (isinstance(no, ast.Attribute) and no.attr == "email"):
                    continue
                base = no.value
                if isinstance(base, ast.Attribute) and base.attr == "user":
                    infracoes.append(
                        f"{caminho.relative_to(raiz)}:{no.lineno} le `…user.email`"
                    )

        # AS DUAS leituras de endereço a partir de uma inscrição que existem no
        # projeto, e as duas estão em `services.py`:
        #
        #   1. o ENVIO do resumo, e
        #   2. o e-mail de CONFIRMAÇÃO (double opt-in, 2026-10-02).
        #
        # A segunda é legítima e tem a mesma defesa de leitura que a primeira:
        # `_enviar_email_de_confirmacao` só é chamado de dentro de
        # `inscrever_com_status`, e essa função grava a linha com
        # `user=user` (ela não sabe sobre linhas anonimizadas) — mas
        # `_localizar_por_hash_de_confirmacao` só devolve linhas
        # `confirmado_em IS NULL`, e uma linha revogada tem `user=None` por
        # `_campos_de_revogacao`. Nenhuma das duas enxerga um registro
        # anonimizado.
        #
        # Qualquer TERCEIRA ocorrência é um caminho novo — e um caminho novo é
        # exatamente o que este teste existe para bloquear. A lista é
        # explícita e não por função: uma lista "calculada" que derivasse as
        # linhas do próprio código passaria a aprovar o caminho novo. E a
        # comparação é por conjunto (`sorted`), não por ordem: a ordem em que
        # `ast.walk` encontra as duas leituras é um detalhe da árvore sintática,
        # e um teste que reprova por causa dele é um teste que quebraria por uma
        # refatoração que não tem nada a ver com anonimização.
        assert sorted(infracoes) == sorted(
            [
                f"newsletter/services.py:{_linha_do_envio()} le `…user.email`",
                f"newsletter/services.py:{_linha_da_confirmacao()} le `…user.email`",
            ]
        ), f"um novo caminho de leitura de e-mail a partir da inscrição: {infracoes}"

    def test_o_envio_so_enxerga_inscricao_vinculada_e_ativa(self):
        """
        A defesa de profundidade: mesmo que alguém reintroduza a leitura, o
        filtro do envio não deixa uma inscrição anonimizada chegar nela.
        """
        from config.tests.backends import EntregaSimuladaBackend, caminho_de
        from django.core import mail

        _, inscricao = _inscrito()
        mail.outbox.clear()
        EntregaSimuladaBackend.entregues.clear()
        _revogar(inscricao)

        with override_settings(EMAIL_BACKEND=caminho_de(EntregaSimuladaBackend)):
            envio = services.enviar_newsletters()

        assert envio.total_inscricoes_processadas == 0
        assert envio.total_enviados == 0
        assert mail.outbox == []
        assert EntregaSimuladaBackend.entregues == []


def _linha_do_envio() -> int:
    """Linha do `recipient_list=[inscricao.user.email]` em `services.py`."""
    return _linha_da_leitura(services.enviar_newsletters)


def _linha_da_confirmacao() -> int:
    """Linha do `destinatario = inscricao.user.email` em `services.py`."""
    return _linha_da_leitura(services._enviar_email_de_confirmacao)


def _linha_da_leitura(objeto) -> int:
    """Linha em que a função recebida lê `…user.email` de uma inscrição."""
    import inspect

    from newsletter import services as s

    fonte, inicio = inspect.getsourcelines(objeto)
    for deslocamento, linha in enumerate(fonte):
        if ".user.email" in linha:
            return inicio + deslocamento
    raise AssertionError(
        f"{objeto.__name__} não lê mais `…user.email` — se a leitura foi "
        "removida, este teste precisa ser revisto junto com ela"
    )


# ---------------------------------------------------------------------------
# 3. A prova sobrevive
# ---------------------------------------------------------------------------


class TestAProvaSobrevive:

    def test_as_datas_de_concessao_e_revogacao_continuam(self):
        _, inscricao = _inscrito()
        concessao = inscricao.consentimento_aceito_em
        assert concessao is not None

        _revogar(inscricao)

        assert inscricao.consentimento_aceito_em == concessao, (
            "a data do consentimento não pode ser apagada junto com o dado pessoal"
        )
        assert inscricao.consentimento_revogado_em is not None
        assert inscricao.consentimento_aceito_em < inscricao.consentimento_revogado_em

    def test_o_registro_responde_as_perguntas_de_auditoria_sem_nenhum_dado_pessoal(self):
        """
        A pergunta que o encarregado de dados faz, e a resposta que a linha dá.

        "Houve consentimento? Quando? Foi revogado? Quando? A pessoa ainda é
        identificável a partir daqui?" — as quatro primeiras com duas colunas
        de data, a quinta com um `user_id is None`.
        """
        _, inscricao = _inscrito()
        _revogar(inscricao)

        houve = inscricao.consentimento_aceito_em is not None
        quando_concedeu = inscricao.consentimento_aceito_em
        revogado = inscricao.consentimento_revogado_em is not None
        quando_revogou = inscricao.consentimento_revogado_em
        identificavel = inscricao.user_id is not None

        assert houve is True
        assert quando_concedeu is not None
        assert revogado is True
        assert quando_revogou is not None
        assert identificavel is False

    def test_o_escopo_do_consentimento_continua_registrado(self):
        """
        O que a pessoa consentiu em receber também é parte da prova.

        `tipo`, `periodo` e `categorias` dizem QUAL foi a finalidade aceita. Um
        registro de revogação que perdesse isso registraria "revogou", e não
        "revogou o quê".
        """
        from django.utils import timezone

        user = User.objects.create_user(email="escopo@example.com", password="senha123", papel="free")
        user.consentimento_aceito_em = timezone.now()
        user.save(update_fields=["consentimento_aceito_em"])
        inscricao = inscricao_confirmada_para(
            user,
            InscricaoNewsletter.TIPO_CATEGORIA,
            categorias=["esportes"],
            periodo=InscricaoNewsletter.PERIODO_NOITE,
        )
        _revogar(inscricao)

        assert inscricao.tipo == "categoria"
        assert inscricao.periodo == "noite"
        assert inscricao.categorias == ["esportes"]
        # A pessoa não era premium nem precisou ser: o `papel` do titular NÃO
        # foi copiado para a linha, e isso é o certo — copiar dado pessoal de
        # uma pessoa para um registro que sobrevive a ela seria o contrário de
        # minimização.
        assert not hasattr(inscricao, "papel")


# ---------------------------------------------------------------------------
# 4. Os DOIS caminhos de revogação
# ---------------------------------------------------------------------------


class TestOsDoisCaminhosRevogamIgual:

    def test_o_endpoint_autenticado_anonimiza_tambem(self):
        user, inscricao = _inscrito()
        services.cancelar_inscricao(user)
        inscricao.refresh_from_db()

        assert inscricao.ativa is False
        assert inscricao.user_id is None
        assert inscricao.consentimento_revogado_em is not None
        assert inscricao.anonimizado_em is not None
        assert inscricao.consentimento_aceito_em is not None

    def test_os_dois_caminhos_produzem_o_mesmo_registro(self):
        """A comparação é de CONTEÚDO, não de id: os dois têm de produzir a
        mesma forma de registro, senão um deles é um contorno do outro."""
        user_a, por_token = _inscrito("a@example.com")
        _revogar(por_token)

        user_b = User.objects.create_user(email="b@example.com", password="senha123", papel="free")
        user_b.consentimento_aceito_em = _agora()
        user_b.save(update_fields=["consentimento_aceito_em"])
        por_endpoint = inscricao_confirmada_para(user_b, InscricaoNewsletter.TIPO_PADRAO)
        services.cancelar_inscricao(user_b)
        por_endpoint.refresh_from_db()

        campos = [
            "ativa",
            "user_id",
            "tipo",
            "periodo",
        ]
        for campo in campos:
            assert getattr(por_token, campo) == getattr(por_endpoint, campo), campo
        for campo in ("consentimento_aceito_em", "consentimento_revogado_em", "anonimizado_em"):
            assert getattr(por_token, campo) is not None, campo
            assert getattr(por_endpoint, campo) is not None, campo


# ---------------------------------------------------------------------------
# 5. A fronteira, declarada
# ---------------------------------------------------------------------------


class TestAFronteiraDeclarada:

    def test_a_conta_continua_existindo_e_isso_e_uma_decisao_nao_um_esqueciço(self):
        """
        A afirmação mais importante deste arquivo, e ela é uma afirmação
        sobre o que o item NÃO fez.

        O endereço continua em `identidade.User.email`. A conta existe, e a
        conta precisa do endereço para login (`USERNAME_FIELD = "email"`),
        redefinição de senha e todo o resto.

        Apagar o endereço da conta é o DIREITO À ELIMINAÇÃO (art. 18 da LGPD) —
        um direito diferente do direito de revogar o consentimento de newsletter
        (art. 8º, V). Forçá-lo aqui apagaria o acesso, o histórico e o cadastro
        em Communities de quem pediu apenas para parar de receber newsletter.

        Este teste existe para que ninguém leia "o e-mail não é mais recuperável
        pelo registro da newsletter" e conclua "o e-mail não existe mais no
        portal". São duas afirmações diferentes, e só a primeira é verdade.
        """
        user, inscricao = _inscrito()
        _revogar(inscricao)

        # A conta segue existindo, com o seu endereço — outro registro, outra
        # base legal, fora da autoridade deste módulo.
        conta = User.objects.get(pk=user.pk)
        assert conta.email == ENDERECO

        # E a garantia que este item entrega é a outra, e ela é verificável:
        # a PARTIR do registro anonimizado, não há caminho para o endereço.
        inscricao.refresh_from_db()
        assert inscricao.user_id is None
        assert not InscricaoNewsletter.objects.filter(user_id=user.pk).exists()

    def test_a_reinscricao_cria_um_registro_novo_e_nao_reaproveita_o_antigo(self):
        """
        Cada ato de consentimento é um registro próprio.

        Como a revogação cortou o vínculo, a reinscrição não pode — e não deve —
        reaproveitar a linha. Uma linha que liga e desliga é um campo, não um
        registro; e é a linha que guarda a prova de que o consentimento existiu.
        """
        user, inscricao = _inscrito()
        _revogar(inscricao)

        inscricao_confirmada_para(user, InscricaoNewsletter.TIPO_PADRAO)

        assert InscricaoNewsletter.objects.count() == 2
        nova = InscricaoNewsletter.objects.get(user=user)
        assert nova.pk != inscricao.pk
        assert nova.ativa is True
        assert nova.consentimento_revogado_em is None
        assert nova.anonimizado_em is None
        # E as duas linhas coexistem: a revogada é a prova, a nova é a
        # concessão vigente.
        inscricao.refresh_from_db()
        assert inscricao.ativa is False
        assert inscricao.consentimento_revogado_em is not None
