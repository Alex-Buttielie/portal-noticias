"""
Fábrica de inscrições da newsletter — double opt-in (2026-10-02).

POR QUE ESTE ARQUIVO EXISTE
==========================
Até 2026-10-02, `services.inscrever(...)` devolvia uma inscrição `ativa=True` e
pronta para receber. A partir do double opt-in, a mesma chamada devolve uma
PENDENTE: `ativa=False`, `confirmado_em=None`, e um e-mail de confirmação
enviado. Os testes que existiam medem coisas que continuam verdadeiras — o
envio, o descadastro, a anonimização, o rate limit — mas chegaram até elas
por uma porta que fechou.

Este arquivo é a porta nova, e ele existe em vez de "consertar cada teste" por
uma razão que é a mesma que motivou `_campos_de_revogacao`: a transformação
ficar em UM lugar é o que impede que um teste use um caminho e outro use o
outro. Cada teste aqui ou confirma explicitamente, ou diz que está testando o
portão.

O QUE ESTE ARQUIVO NÃO FAZ
==========================
**Não contorna o portão.** `confirmar()` grava `confirmado_em` e `ativa=True`
direto, como o `update_or_create` faria depois do clique. Isso é deliberado e é
o que permite escrever testes do ENVIO sem mandar e-mail de confirmação a cada
um deles. Os testes do portão NÃO usam este arquivo para o caminho de escrita:
eles chamam `services.inscrever` de verdade, com o backend que devem.

A consequência é que `confirmar()` e `services.confirmar_por_token` precisam
concordar. `test_confirmar_e_o_caminho_real_para_o_estado_confirmado` trava
essa concordância — e é um teste que reprova se alguém ajustar um dos dois sem
ajustar o outro.
"""

from __future__ import annotations

from django.utils import timezone

from newsletter import services
from newsletter.models import InscricaoNewsletter


def confirmar(inscricao) -> InscricaoNewsletter:
    """Põe a inscrição no estado CONFIRMADO, como o clique faria.

    Não manda e-mail e não depende de canal: é a escrita de estado, e não o
    caminho inteiro. Quem precisa do caminho inteiro (e da prova de que o
    e-mail sai) usa `services.confirmar_por_token` com o token gerado, que é o
    que `test_double_optin_confirmacao.py` faz.
    """
    InscricaoNewsletter.objects.filter(pk=inscricao.pk).update(
        ativa=True,
        confirmado_em=timezone.now(),
        consentimento_aceito_em=timezone.now(),
    )
    inscricao.refresh_from_db()
    return inscricao


def inscricao_confirmada(user, tipo=InscricaoNewsletter.TIPO_PADRAO, **kwargs):
    """Atalho: `inscrever` + `confirmar`. Devolve a inscrição confirmada.

    Para os testes cujo assunto é o que acontece DEPOIS da confirmação. Para os
    que são sobre a inscrição em si, o par explícito
    (`services.inscrever` e depois as asserções sobre `estado()`) é mais legível
    e é o que os novos testes fazem.
    """
    inscricao = services.inscrever(user, tipo, **kwargs)
    limpar_emails()
    return confirmar(inscricao)


#: Alias com o mesmo nome de antes nos testes P1-06, para que a substituição
#: mecânica (`services.inscrever` → esta função) deixe um texto que DIZ o que
#: passou a acontecer. Um teste do envio que lê `inscricao_confirmada_para(...)`
#: está dizendo, na própria linha, que precisou confirmar antes — que era
#: silencioso antes do double opt-in e não é mais.
inscricao_confirmada_para = inscricao_confirmada


def limpar_emails() -> None:
    """Esvazia `mail.outbox` e o registro do dublê que entrega.

    Existe por um motivo concreto, e não por preguiça: `services.inscrever`
    agora ENTREGA um e-mail (o de confirmação), e os testes do ENVIO afirmam
    coisas como `len(mail.outbox) == 1` — querendo dizer "um resumo foi
    entregue", e passando a ver dois, porque a caixa ainda tem o e-mail de
    confirmação da montagem do cenário.

    Sem esta função, a correção seria encher os testes de envio de
    `mail.outbox.clear()` repetido — oito vezes, em oito lugares, com a chance
    de alguém esquecer uma. E o pior: um teste que NÃO limpasse passaria por
    acidente com `total_enviados` certo e `len(outbox)` errado a mais, e a
    próxima pessoa não saberia se era bug ou cenário.

    Ela é chamada pelo próprio `inscricao_confirmada_para`, ou seja, no ponto
    em que a montagem do cenário TERMINA. Um teste que QUER ver o e-mail de
    confirmação não usa esta função — usa `services.inscrever` direto, e é
    assim que os testes do portão e da confirmação são escritos.
    """
    from django.core import mail

    from config.tests.backends import EntregaSimuladaBackend

    mail.outbox.clear()
    EntregaSimuladaBackend.entregues.clear()


def ultima_inscricao(user) -> InscricaoNewsletter:
    """A inscrição VINCULADA a este usuário, relida do banco.

    Lê do banco de propósito: os testes de double opt-in inspecionam muito
    `ativa` e `confirmado_em` logo depois de uma escrita feita por
    `QuerySet.update()`, e inspecionar o objeto em memória mostraria o valor
    antigo. Um teste que passa com o objeto velho e falha com o relido é um
    teste que não viu a mudança que alegava medir.
    """
    return InscricaoNewsletter.objects.get(user=user)