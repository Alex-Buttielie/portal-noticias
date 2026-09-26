"""Serviço de domínio de newsletter (run 20260902-1515-newsletter; P1-06).

O QUE ESTE MÓDULO PASSA A GARANTIR (P1-06)
==========================================
1. **Consentimento é pré-requisito da inscrição, não só do envio.** `inscrever()`
   recusa quem não tem `User.consentimento_aceito_em` (que o cadastro em
   `identidade/serializers.py:71` grava sempre, com data). Antes, uma conta sem
   consentimento conseguia criar uma inscrição `ativa=True`; só o envio a
   filtrava — e o filtro é de LEITURA, então qualquer tela futura que liste
   inscrições sem ele trataria essa pessoa como inscrita.
2. **O descadastro não revela cadastro.** `descadastrar_por_token` devolve
   `True` sempre que um token foi *apresentado* e `False` só quando nenhum
   token foi apresentado — condição que não depende do banco. A view responde
   idêntico para token válido, inválido, expirado e já usado.
3. **O token é de uso único e expira** (`newsletter/tokens.py`). No uso, o
   segredo do banco é rotacionado no mesmo `UPDATE` que desativa a inscrição.
4. **A entrega não é reportada quando não aconteceu.** Um `EMAIL_BACKEND` que
   não entrega a ninguém (console, locmem, dummy, filebased) NÃO conta como
   `total_enviados` — a mesma regra de `contato/` (P0-02c, furo 3) aplicada ao
   caminho que já está em produção. Ver `enviar_newsletters`.

O QUE ESTE MÓDULO NÃO CONSEGUE GARANTIR (Pendência jurídica, ver relatório P1-06)
===============================================================================
Não existe registro datado da revogação do consentimento, nem da versão do
texto aceitoSpecifically para a newsletter. O que existe é
`InscricaoNewsletter.ativa=False` (o efeito, que é real e é o que impede o
envio) e `atualizado_em` (auto_now) como **proxy** da data da revogação — que se
perde se algo reescrever a inscrição depois. `User.consentimento_aceito_em` +
`User.consentimento_versao_termos` datam o aceite dos Termos no cadastro, que é
outra finalidade. Fechar isso exige migration, que este item não pode criar.
"""

from __future__ import annotations

import hmac
import logging

from django.conf import settings
from django.core.mail import send_mail

from contato.services import BACKENDS_SEM_ENTREGA_REAL
from feed.services import itens_publicaveis
from gating.services import has_feature
from radar.services import tendencias as radar_tendencias

from .models import EnvioNewsletter, InscricaoNewsletter, gerar_token
from .tokens import gerar_token_descadastro, hash_do_segredo, ler_hash_do_token

logger = logging.getLogger(__name__)


class RecursoGatedError(Exception):
    pass


class ConsentimentoAusenteError(Exception):
    """A pessoa não tem consentimento registrado — a inscrição é recusada.

    Existe separada de `RecursoGatedError` porque as duas se confundiriam na
    resposta HTTP se fossem o mesmo erro: "é recurso Premium" pede para voltar
    depois; "não há base legal registrada" é outra decisão, com outro texto.
    """


def _tem_consentimento(user) -> bool:
    return getattr(user, "consentimento_aceito_em", None) is not None


def inscrever(user, tipo, categorias=None, periodo=None) -> InscricaoNewsletter:
    """Inscrição (criando ou atualizando). Ver `inscrever_com_status` para o
    booleano `criado`."""
    inscricao, _criado = inscrever_com_status(user, tipo, categorias, periodo=periodo)
    return inscricao


def inscrever_com_status(user, tipo, categorias=None, periodo=None):
    """`inscrever` + o booleano `criado` do `update_or_create`.

    `update_or_create` nunca duplica: `InscricaoNewsletter.user` é
    `OneToOneField` (`newsletter/models.py:35`) e o filtro é por `user`, então a
    segunda inscrição do MESMO e-mail atualiza a linha existente. O que muda na
    segunda vez é o status HTTP: anunciar `201 Created` quando nada foi criado
    mente sobre o que o servidor fez — mesmo motivo que fez `landing/` responder
    200 na segunda vez (`landing/views.py:34-35`).
    """
    if not _tem_consentimento(user):
        raise ConsentimentoAusenteError(
            "Não há consentimento registrado para esta conta; a inscrição na "
            "newsletter exige aceite explícito."
        )
    if tipo == InscricaoNewsletter.TIPO_PERSONALIZADA and not has_feature(user, "newsletter_personalizada"):
        raise RecursoGatedError("Newsletter personalizada é um recurso Premium.")
    defaults = {"tipo": tipo, "categorias": categorias or [], "ativa": True}
    if periodo:
        defaults["periodo"] = periodo
    inscricao, criado = InscricaoNewsletter.objects.update_or_create(user=user, defaults=defaults)
    if criado:
        # Auditoria do ato de consentir, sem e-mail e sem token: o `request_id`
        # já entra em toda linha pelo `RequestIdLogFilter`, e a origem do
        # consentimento é `User.consentimento_aceito_em`, consultável e datado.
        logger.info("newsletter: inscrição criada (inscricao=%s)", inscricao.pk)
    return inscricao, criado


def cancelar_inscricao(user) -> None:
    InscricaoNewsletter.objects.filter(user=user).update(ativa=False)


def _localizar_por_hash(hash_assinado: str):
    """Inscrição cujo segredo do banco produz `hash_assinado`, ou `None`.

    O segredo do banco nunca sai do processo, então não existe coluna indexável
    para o hash: a comparação é feita em Python, sobre as inscrições candidatas.
    A lista é pequena por construção (um segredo por inscrição) e o custo é
    irrelevante ao lado do envio de e-mail que vem depois.
    """
    for inscricao in InscricaoNewsletter.objects.only("pk", "token_descadastro", "ativa"):
        segredo = inscricao.token_descadastro
        if not segredo:
            continue
        if hmac.compare_digest(hash_do_segredo(segredo), hash_assinado):
            return inscricao
    return None


def descadastrar_por_token(token: str) -> bool:
    """Cancela a inscrição pelo link do e-mail. Sem login, sem revelar cadastro.

    O retorno é `True` sempre que um token foi **apresentado** e `False` só
    quando nenhum token foi apresentado — condição que não consulta o banco.
    Consequentemente a view responde idêntico para token válido, inexistente,
    expirado e já usado: um atacante que chute tokens não consegue distinguir
    "acertou um cadastro" de "errou", que é o vazamento que existia antes.

    `True` significa "pedido processado", **não** "havia inscrição".

    Uso único: o mesmo `UPDATE` que grava `ativa=False` rotaciona
    `token_descadastro`. O filtro do `UPDATE` é o segredo ANTIGO, então a
    operação é atômica — dois POSTs simultâneos do mesmo token não podem
    revogar duas vezes nem reverter nada. `atualizado_em` (auto_now) recebe o
    instante da revogação.
    """
    hash_assinado = ler_hash_do_token(token)
    if hash_assinado is None:
        return False

    inscricao = _localizar_por_hash(hash_assinado)
    if inscricao is None:
        return False

    ja_estava_inativa = not inscricao.ativa
    rotacionado = InscricaoNewsletter.objects.filter(
        pk=inscricao.pk, token_descadastro=inscricao.token_descadastro
    ).update(ativa=False, token_descadastro=gerar_token())
    if not rotacionado:
        # Corrida: outra requisição rotacionou o segredo entre o SELECT e o
        # UPDATE. O efeito desejado já foi alcançado por ela.
        return False

    # O que o operador precisa: que houve revogação, e de qual inscrição. O que
    # ele NÃO precisa: o e-mail, o token, ou o corpo do e-mail enviado. Este
    # log é o que faltava — sem ele não há "quando" nem "quem" para responder a
    # um titular que pergunta por que ainda recebe.
    logger.info(
        "newsletter: consentimento revogado por token (inscricao=%s, ja_estava_inativa=%s)",
        inscricao.pk,
        ja_estava_inativa,
    )
    return True


def _categorias_distintas(valores) -> list:
    """Remove repetições preservando a ordem em que a pessoa escolheu.

    A UI não repete categoria (`NewsletterForm.tsx:93-95` alterna o botão), mas a
    API não depende da UI: `POST {"categorias": ["esportes", "esportes"]}`
    repetia a MESMA notícia duas vezes no corpo do e-mail (medido antes desta
    correção). Além do efeito visual, o titular receberia a mesma manchete
    duplicada sem ter pedido nada.
    """
    vistas = set()
    unicas = []
    for valor in valores or []:
        chave = str(valor).strip().casefold()
        if not chave or chave in vistas:
            continue
        vistas.add(chave)
        unicas.append(valor)
    return unicas


def _itens_para_inscricao(inscricao: InscricaoNewsletter, limite=10):
    """Critério de aceite 2."""
    if inscricao.tipo == InscricaoNewsletter.TIPO_CATEGORIA and inscricao.categorias:
        itens = []
        for categoria in _categorias_distintas(inscricao.categorias):
            itens.extend(list(itens_publicaveis(categoria=categoria)[:limite]))
        return itens[:limite]
    if inscricao.tipo == InscricaoNewsletter.TIPO_PERSONALIZADA:
        interesses = getattr(inscricao.user, "interesses", []) or []
        itens = []
        for interesse in _categorias_distintas(interesses):
            itens.extend(list(itens_publicaveis(categoria=interesse)[:limite]))
        return itens[:limite] or list(itens_publicaveis()[:limite])
    return list(itens_publicaveis()[:limite])


def montar_corpo_email(inscricao: InscricaoNewsletter) -> str:
    """Critério de aceite 3 — sempre inclui link para a fonte original de cada item."""
    itens = _itens_para_inscricao(inscricao)
    linhas = ["Resumo do Portal de Notícias", ""]
    for item in itens:
        linhas.append(f"- {item.titulo} ({item.nome_fonte}): {item.url_fonte_original}")

    # BRD seção 27 — "Radar de tendências" é um item explícito do conteúdo
    # da newsletter, junto com "Principais acontecimentos" e "Links para
    # fontes originais" (já cobertos acima). Gap real encontrado na análise do
    # BRD: a newsletter nunca incluía nada do Radar. Reaproveita
    # `radar.services.tendencias()` (recorte nacional, sem filtro de
    # localidade — a inscrição de newsletter não guarda localidade própria)
    # e lista as 3 categorias com mais cobertura.
    assuntos = radar_tendencias().get("assuntos_em_alta", [])[:3]
    if assuntos:
        linhas.append("")
        linhas.append("Radar de tendências — assuntos em alta:")
        for assunto in assuntos:
            linhas.append(f"- {assunto['categoria']}: {assunto['numero_noticias']} notícia(s)")

    linhas.append("")
    linhas.append(f"Veja mais e assine o Premium: {settings.FRONTEND_BASE_URL}/planos")
    linhas.append(
        f"Para descadastrar: {settings.FRONTEND_BASE_URL}/newsletter/descadastrar"
        f"?token={gerar_token_descadastro(inscricao)}"
    )
    return "\n".join(linhas)


def canal_entrega_real() -> bool:
    """Diz se o `EMAIL_BACKEND` configurado entrega e-mail a alguém de verdade.

    Mesmo critério de `contato/services.py:verificar_canal` (P0-02c, furo 3) e
    a MESMA lista (`BACKENDS_SEM_ENTREGA_REAL`), para que os dois caminhos não
    possam divergir: `newsletter/tests/test_p1_06_consentimento.py` trava essa
    igualdade.

    Isto importa mais aqui do que no contato, porque a suíte de testes NUNCA
    vê um backend que entrega: `django.test.utils.setup_test_environment()`
    (`django/test/utils.py:146-147`) **sobrescreve** `settings.EMAIL_BACKEND` com
    `locmem` no início de toda sessão de teste, e `locmem` não entrega a ninguém.
    Sem esta checagem, `total_enviados` contaria "entregas" que foram só para
    um dicionário em memória.
    """
    return (getattr(settings, "EMAIL_BACKEND", "") or "").strip() not in BACKENDS_SEM_ENTREGA_REAL


def enviar_newsletters(periodo: str | None = None) -> EnvioNewsletter:
    """
    Critérios de aceite 5, 6 — resiliente a falha individual; respeita
    consentimento e inscrição ativa. `periodo` (BRD seção 27 — "Resumo da
    manhã"/"Resumo da noite"): quando informado, envia só para inscrições
    daquele período (usado pelos 2 agendamentos de Celery Beat separados,
    manhã e noite); `None` envia para todas as inscrições ativas,
    independente do período — usado por `manage.py`/testes manuais.

    P1-06 — a contagem é honesta:

    * `total_enviados` conta só o que foi entregue a um canal real. Com
      `EMAIL_BACKEND` em console/locmem/dummy/filebased, o envio é **não
      tentado** e a inscrição conta como `total_falhas`, com um ERROR que diz
      qual configuração falta. O estado gravado passa a ser "não entregue" em
      vez de "1 enviado" — a mentira que o `contato/` já se recusou a contar
      (P0-02c) e que aqui continuava em produção.
    * `total_falhas` conta "não entregue", o que inclui tanto a recusa do
      provedor quanto a ausência de canal. Os dois são a mesma coisa para quem
      lê o número: nada chegou.
    """
    filtros = {"ativa": True, "user__consentimento_aceito_em__isnull": False}
    if periodo:
        filtros["periodo"] = periodo
    inscricoes = list(InscricaoNewsletter.objects.filter(**filtros).select_related("user"))

    total_enviados = 0
    total_falhas = 0

    if inscricoes and not canal_entrega_real():
        # Uma vez por execução, não uma vez por inscrição: o motivo é o mesmo
        # para todas, e repetir a frase por inscrição só inflaria o log com o
        # mesmo texto. O nome do backend entra (o operador precisa saber qual
        # configurar); a chave do Resend e os endereços, nunca.
        logger.error(
            "newsletter: NENHUMA newsletter foi entregue — DJANGO_EMAIL_BACKEND=%s "
            "não entrega e-mail a ninguém (só imprime, guarda em memória ou "
            "descarta). As %d inscrições ativas com consentimento ficam sem "
            "receber nada e esta execução é registrada como falha, não como "
            "envio. Defina DJANGO_EMAIL_BACKEND=config.email_resend."
            "ResendEmailBackend e RESEND_API_KEY=re_... antes de tratar o envio "
            "como entregue (estado da integração: PROD_DECISOES.md, item 2).",
            getattr(settings, "EMAIL_BACKEND", "(vazio)"),
            len(inscricoes),
        )
        return EnvioNewsletter.objects.create(
            total_inscricoes_processadas=len(inscricoes),
            total_enviados=0,
            total_falhas=len(inscricoes),
        )

    for inscricao in inscricoes:
        try:
            enviados = send_mail(
                subject="Seu resumo do Portal de Notícias",
                message=montar_corpo_email(inscricao),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[inscricao.user.email],
                fail_silently=False,
            )
        except Exception as exc:  # noqa: BLE001 — uma falha não para o lote
            # Log mínimo: TIPO da exceção, sem `str(exc)` e sem traceback. O
            # texto de erro de um backend de e-mail real ecoa o destinatário
            # (`SMTPServerDisconnected: ... b'...@exemplo.com' ...`), e o
            # endereço de quem recebe newsletter é dado pessoal — não vai
            # para o log. Sem corpo de mensagem, sem token, sem credencial.
            logger.error(
                "newsletter: exceção do provedor de e-mail (inscricao=%s, tipo=%s)",
                inscricao.pk,
                type(exc).__name__,
            )
            total_falhas += 1
            continue

        if not enviados:
            total_falhas += 1
            continue
        total_enviados += 1

    return EnvioNewsletter.objects.create(
        total_inscricoes_processadas=len(inscricoes),
        total_enviados=total_enviados,
        total_falhas=total_falhas,
    )
