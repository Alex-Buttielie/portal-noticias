"""
Ponto único de mutação de estado do app `identidade/` (convenção DDD do
projeto: toda mutação passa por `services.py`, views nunca escrevem direto
nos models). Este arquivo nasceu nesta run (20260903-1134-seo-lgpd-design-
system) para a nova funcionalidade de preferências de cookies — o restante
das views deste app (cadastro, login, onboarding etc.) já existia antes desta
run e não foi tocado/refatorado aqui (fora do escopo desta run, ver
implementation-history.md).
"""

from __future__ import annotations

from django.utils import timezone

CATEGORIAS_OPCIONAIS = ("analytics", "personalizacao")

#: Throttle de `atualizar_last_seen` (implementation-contract.md run
#: 20261013-1048-home-radar-central-ux, Bloco C, C-07 — restrição de
#: performance: nunca um UPDATE por requisição autenticada).
LAST_SEEN_THROTTLE_SEGUNDOS = 60

#: Janela de "ativo agora" usada por `identidade.services.contar_usuarios_ativos_agora`
#: e pela Central (`/admin` — dashboard raiz).
ATIVO_AGORA_JANELA_MINUTOS = 5


def atualizar_preferencias_cookies(user, categorias: dict) -> "identidade.models.User":  # noqa: F821
    """
    Persiste a escolha de cookies não essenciais de um usuário autenticado
    (implementation-contract.md, escopo B). `categorias` só pode conter as
    chaves em `CATEGORIAS_OPCIONAIS` — "essenciais" nunca é aceito aqui
    porque é sempre ativo, não é uma escolha armazenável.
    """
    preferencias = {chave: bool(categorias.get(chave, False)) for chave in CATEGORIAS_OPCIONAIS}
    user.preferencias_cookies = preferencias
    user.preferencias_cookies_atualizado_em = timezone.now()
    user.save(update_fields=["preferencias_cookies", "preferencias_cookies_atualizado_em"])
    return user


def atualizar_objetivo_assinatura(user, texto: str) -> "identidade.models.User":  # noqa: F821
    """
    Persiste o objetivo da assinatura Premium (por que o usuário assinou,
    em texto livre do próprio usuário). Chamada por
    `assinatura.views.ObjetivoAssinaturaView`, que já garante via
    `gating.services.exigir_feature` que só usuário Premium chega aqui.
    """
    user.objetivo_assinatura = (texto or "").strip()[:500]
    user.objetivo_assinatura_atualizado_em = timezone.now()
    user.save(update_fields=["objetivo_assinatura", "objetivo_assinatura_atualizado_em"])
    return user


def atualizar_last_seen(user) -> None:
    """
    Atualiza `User.last_seen` de forma barata (chamado por
    `identidade.middleware.AtualizarUltimoAcessoMiddleware` em TODA
    requisição autenticada — por isso o throttle é obrigatório, não
    opcional): só grava um `UPDATE` quando passaram
    `LAST_SEEN_THROTTLE_SEGUNDOS` desde o último valor conhecido.

    Usa `.update()` direto no queryset (não `user.save()`) por dois
    motivos: (1) evita reescrever a linha inteira (ex.: senha, papel) a
    partir de uma instância de `request.user` potencialmente desatualizada
    de outra requisição concorrente; (2) é um `UPDATE` de uma única coluna,
    sem disparar nenhum signal de `save()` do modelo.
    """
    agora = timezone.now()
    ultimo = user.last_seen
    if ultimo is not None and (agora - ultimo).total_seconds() < LAST_SEEN_THROTTLE_SEGUNDOS:
        return
    type(user).objects.filter(pk=user.pk).update(last_seen=agora)
    # Mantém a instância em memória coerente para o restante desta mesma
    # requisição (ex.: se algo mais tarde no mesmo request ler
    # `request.user.last_seen`) — best-effort, não previne todas as corridas
    # entre threads/processos, o que é aceitável para telemetria.
    user.last_seen = agora


def contar_usuarios_ativos_agora(janela_minutos: int = ATIVO_AGORA_JANELA_MINUTOS) -> int:
    """
    Quantos usuários têm `last_seen` dentro da janela de "ativo agora"
    (critério de aceite 12 do implementation-contract.md). Não é presença em
    tempo real (fora de escopo, ver não-objetivos do contrato) — é uma
    contagem por polling/requisição, documentada e ajustável via o
    parâmetro `janela_minutos`.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    limite = timezone.now() - timezone.timedelta(minutes=janela_minutos)
    return User.objects.filter(last_seen__gte=limite).count()


def criar_usuario_admin(*, email: str, senha: str, nome: str = "", papel: str | None = None, is_active: bool = True):
    """
    Cria uma conta diretamente pelo admin (Central — C-01), fora do fluxo
    público de cadastro/verificação por e-mail (`identidade.views.CadastroView`).

    Pressupõe que o CHAMADOR já validou e-mail único e senha forte — ver
    `painel_admin.serializers.UsuarioCriacaoSerializer`, que reaproveita o
    MESMO `django.contrib.auth.password_validation.validate_password` usado
    por `identidade.serializers.CadastroSerializer.validate_senha` (a
    "validação já existente" citada no contrato). Esta função não revalida
    de propósito — o padrão do app é `CadastroSerializer.create()` também
    assumir `validated_data` já validado pela serializer.

    Diferenças deliberadas em relação ao cadastro público:
    - `email_verificado=True`: o admin está vouching pela conta — não há
      e-mail de verificação a confirmar (e esta função nunca envia e-mail).
    - `deve_trocar_senha=True`: a senha definida pelo admin é temporária;
      o usuário troca no primeiro login (mesmo mecanismo de
      `User.deve_trocar_senha` usado para carga administrativa).
    - Sem aceite de termos/consentimento: não é um cadastro self-service;
      `consentimento_aceito_em` fica nulo.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(
        email=email,
        nome=(nome or "").strip(),
        papel=papel or User.PAPEL_FREE,
        is_active=is_active if is_active is not None else True,
        email_verificado=True,
        deve_trocar_senha=True,
    )
    user.set_password(senha)
    user.save()
    return user
