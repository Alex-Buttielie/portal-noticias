from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from moderacao import services
from moderacao.models import AcaoModeracao, Denuncia

pytestmark = pytest.mark.django_db

User = get_user_model()


def _usuario(email):
    return User.objects.create_user(email=email, password="senha123", papel="free")


def test_denunciar_cria_pendente_apontando_para_o_alvo():
    denunciante = _usuario("denunciante@example.com")
    alvo = _usuario("alvo@example.com")  # usa o próprio User como "alvo" genérico neste teste de sanidade

    denuncia = services.denunciar(denunciante, Denuncia.MOTIVO_SPAM, comentario=alvo)

    assert denuncia.status == Denuncia.STATUS_PENDENTE
    assert denuncia.alvo == alvo


def test_resolver_denuncia_exige_moderador_e_registra_decisao():
    denunciante = _usuario("denunciante2@example.com")
    alvo = _usuario("alvo2@example.com")
    moderador = _usuario("mod@example.com")
    denuncia = services.denunciar(denunciante, Denuncia.MOTIVO_OUTRO, comentario=alvo)

    resolvida = services.resolver_denuncia(denuncia, moderador, procedente=True, motivo="confirmado")

    assert resolvida.status == Denuncia.STATUS_PROCEDENTE
    assert resolvida.resolvido_por == moderador


def test_aplicar_acao_exige_moderador_humano():
    alvo = _usuario("alvo3@example.com")
    with pytest.raises(ValueError):
        services.aplicar_acao(alvo, AcaoModeracao.TIPO_AVISO, "teste", aplicado_por=None)


def test_aplicar_acao_gera_evento_de_reputacao_negativo():
    alvo = _usuario("alvo4@example.com")
    moderador = _usuario("mod2@example.com")

    services.aplicar_acao(alvo, AcaoModeracao.TIPO_BLOQUEIO_TEMP, "spam recorrente", aplicado_por=moderador)

    reputacao = services.obter_reputacao(alvo)
    assert reputacao.pontuacao == 70  # 100 - 30


def test_reputacao_baseline_padrao_para_usuario_novo():
    usuario = _usuario("novo@example.com")
    reputacao = services.obter_reputacao(usuario)
    assert reputacao.pontuacao == 100
    assert reputacao.nivel == "confiavel"


# ---------------------------------------------------------------------------
# BRD seção 16 — bloqueios (temporário/permanente) precisam ter efeito real,
# não só existir como registro. Gap real encontrado na análise do BRD:
# nenhum código consultava isto antes desta correção.
# ---------------------------------------------------------------------------


def test_usuario_sem_acoes_de_moderacao_nao_esta_bloqueado():
    usuario = _usuario("livre@example.com")
    assert services.usuario_esta_bloqueado(usuario) is False


def test_bloqueio_permanente_bloqueia_independente_de_ativo_ate():
    from django.utils import timezone

    usuario = _usuario("bloqueado-perm@example.com")
    moderador = _usuario("mod-perm@example.com")
    services.aplicar_acao(
        usuario, AcaoModeracao.TIPO_BLOQUEIO_PERMANENTE, "violação grave", aplicado_por=moderador
    )
    assert services.usuario_esta_bloqueado(usuario) is True


def test_bloqueio_temporario_com_data_futura_bloqueia():
    from datetime import timedelta

    from django.utils import timezone

    usuario = _usuario("bloqueado-temp@example.com")
    moderador = _usuario("mod-temp@example.com")
    services.aplicar_acao(
        usuario,
        AcaoModeracao.TIPO_BLOQUEIO_TEMP,
        "spam",
        aplicado_por=moderador,
        ativo_ate=timezone.now() + timedelta(days=7),
    )
    assert services.usuario_esta_bloqueado(usuario) is True


def test_bloqueio_temporario_com_data_passada_nao_bloqueia_mais():
    from datetime import timedelta

    from django.utils import timezone

    usuario = _usuario("bloqueio-expirado@example.com")
    moderador = _usuario("mod-exp@example.com")
    services.aplicar_acao(
        usuario,
        AcaoModeracao.TIPO_BLOQUEIO_TEMP,
        "spam",
        aplicado_por=moderador,
        ativo_ate=timezone.now() - timedelta(days=1),
    )
    assert services.usuario_esta_bloqueado(usuario) is False


def test_aviso_e_remocao_nao_contam_como_bloqueio():
    usuario = _usuario("so-aviso@example.com")
    moderador = _usuario("mod-aviso@example.com")
    services.aplicar_acao(usuario, AcaoModeracao.TIPO_AVISO, "primeira ocorrência", aplicado_por=moderador)
    services.aplicar_acao(usuario, AcaoModeracao.TIPO_REMOCAO, "conteúdo removido", aplicado_por=moderador)
    assert services.usuario_esta_bloqueado(usuario) is False
