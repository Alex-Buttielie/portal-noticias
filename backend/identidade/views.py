import logging

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.email_entrega import (
    CanalIndisponivel,
    FalhaDeEntrega,
    registrar_evento,
    verificar_canal_email,
)
from config.throttling import AuthSensivelAnonThrottle, EscritaPublicaAnonThrottle

from . import oauth_google, services
from .emails import (
    DESTINO_REDEFINICAO,
    enviar_email_redefinicao_senha,
    enviar_email_verificacao,
)
from .permissions import IsEmailVerified
from .serializers import (
    CadastroSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    OnboardingSerializer,
    PreferenciasCookiesSerializer,
    RecuperarSenhaSerializer,
    RedefinirSenhaSerializer,
    TrocarSenhaSerializer,
    UserSerializer,
    VerificarEmailSerializer,
)
from .tokens import decode_uidb64, password_reset_token_generator, read_email_verification_token

User = get_user_model()
logger = logging.getLogger(__name__)

# Mensagens genéricas para login/recuperação de senha — não revelam se um
# e-mail está ou não cadastrado (critério de aceite 5 e restrição de
# segurança do implementation-contract.md).
MSG_CREDENCIAIS_INVALIDAS = "E-mail ou senha inválidos."
MSG_RECUPERACAO_GENERICA = (
    "Se o e-mail informado estiver cadastrado, enviaremos instruções de redefinição de senha."
)
# Login social: uma única mensagem para TODAS as recusas de identidade
# (nonce ausente/errado/expirado, `nonce` assinado divergente, e-mail não
# verificado pelo provedor, conta local sem e-mail confirmado). Uma
# mensagem por motivo transformaria o endpoint em oráculo de "esta conta
# existe e está verificada", que é informação de quem é dono do quê.
MSG_OAUTH_NAO_CONCLUIDO = (
    "Não foi possível concluir o login com esta conta. Entre com e-mail e senha."
)
# Ambiente sem `GOOGLE_OAUTH_CLIENT_ID`. Distinto do 400 de credencial
# inválida de propósito: sem o client_id o allauth rejeita TODOS os tokens
# (o `aud` não bate), então tratar isso como "token inválido" esconde a
# causa real e devolve 400 para uma falha de configuração.
MSG_OAUTH_NAO_CONFIGURADO = (
    "O login com Google não está disponível neste ambiente."
)

#: Rótulo da métrica de entrega do fluxo de cadastro.
DESTINO_CADASTRO = "cadastro"

#: Resposta 201 do cadastro. É uma CONSTANTE de propósito: as respostas de
#: "conta criada agora" e de "e-mail já tinha conta" precisam ser idênticas,
#: e a única forma de garantir isso é não interpolar nada vindo do banco.
DETALHE_CADASTRO_OK = "Cadastro realizado. Verifique seu e-mail para confirmar a conta."

#: 503 do cadastro quando não existe canal de entrega real. Diz o que está
#: faltando pelo NOME da configuração (nunca o valor) e que nada foi criado,
#: para a pessoa não ficar achando que a conta existe.
DETALHE_SEM_CANAL = (
    "Seu cadastro não foi concluído e nenhuma conta foi criada: o portal ainda "
    "não está com entrega de e-mail configurada, então o e-mail de verificação "
    "não sairia. Nada foi gravado — tente novamente em instantes. Motivo: {motivos}"
)

#: 503 do cadastro quando o canal existe mas o envio concreto falhou.
DETALHE_FALHA_ENTREGA = (
    "Seu cadastro não foi concluído e nenhuma conta foi criada: não conseguimos "
    "entregar o e-mail de verificação. Nada foi gravado — tente novamente em "
    "instantes."
)


class CadastroView(APIView):
    """POST /api/auth/cadastro/ — cadastro por e-mail/senha (critério de aceite 1).

    O QUE ESTE ENDPOINT GARANTE (P1-04)
    ===================================
    1. **201 só depois de entregue.** O e-mail de verificação precisa ter saído
       para um canal de entrega real. Se não há canal (`console.EmailBackend`
       é o padrão de `config/settings.py:615-617`, e ele só imprime no
       stdout), a resposta é **503** e **nenhuma conta é criada** — o
       cadastro não aconteceu, e a pessoa pode tentar de novo. Era o furo do
       P0-02c: 201 + "Verifique seu e-mail para confirmar a conta" com o
       e-mail apenas impresso no stdout do container.
    2. **O e-mail informado não revela se já tem conta.** Antes deste item,
       `CadastroSerializer.validate_email` devolvia **400** para um e-mail já
       cadastrado e **201** para um e-mail novo — ou seja, um `POST` com
       qualquer senha bastava para enumerar a base. Agora os dois casos
       devolvem a MESMA resposta, byte a byte.

    POR QUE A RESPOSTA NÃO TRAZ MAIS O OBJETO `usuario`
    ==================================================
    A resposta 201 é `{"detail": ...}` e nada mais. Com `usuario` dentro dela,
    as respostas "criado" e "já existia" não podem ser idênticas: o objeto
    carrega `id`, `papel`, `email_verificado` e `date_joined` da conta
    existente, e cada um deles é um oráculo de existência (o pior deles,
    `email_verificado`, distingue "conta criada agora" de "conta já
    verificada"). Não existe campo de `usuario` que seja simultaneamente
    honesto e igual nos dois casos.

    O frontend não usa esse campo: `frontend/app/cadastro/page.tsx:18` chama
    `await api.cadastrar(payload)` e ignora o retorno, usando só o `detail`
    implícito no `setOk(true)`.

    A declaração de tipo do frontend foi AJUSTADA depois (era um follow-up
    que este item não podia fazer, por não poder tocar `frontend/`):
    `cadastrar()` agora devolve `CadastroResposta`, que é só `{ detail }`.
    O `usuario: Usuario` que ainda estava no tipo era uma armadilha armada —
    `request<T>` faz `return corpo as T`, que é uma AFIRMAÇÃO, e não uma
    verificação, então o TypeScript não podia reclamar. O primeiro código que
    lesse `.usuario` receberia `undefined` em runtime, com o compilador
    calado.

    E agora isso está PRESO, não só corrigido:
    `config/tests/test_p1_04_contrato_frontend.py` extrai mecanicamente os
    campos declarados de `frontend/lib/api.ts` e compara com a resposta real
    deste endpoint, nos dois sentidos. Reintroduzir `usuario` no tipo
    reprova a suíte.

    QUANDO O E-MAIL JÁ EXISTE
    =========================
    Nada é criado e nada é sobrescrito (nem papel, nem consentimento, nem
    senha). Se a conta ainda NÃO foi verificada, o e-mail de verificação é
    **reenviado**: sem isso, quem se cadastrou, não verificou, esqueceu e
    tentou de novo receberia um "201, verifique seu e-mail" de um e-mail que
    nunca sairia — exatamente o beco sem saída que este item existe para
    fechar. Se a conta já está verificada, não há o que reenviar.

    A falha de envio nesse ramo de duplicidade **não** muda a resposta, e essa
    é uma escolha deliberada: a alternativa (503 só para e-mail já cadastrado)
    transforma a falha do provedor em oráculo de existência de conta, que é a
    propriedade mais importante deste endpoint. A falha é registrada em
    `logger.error`, em `portal_email_entrega_total{situacao="falha"}` e
    aparece em `/health-detail`. Já o caso **sistêmico** — não existe canal
    nenhum — é verificado ANTES de qualquer consulta ao banco, e devolve 503
    para todo mundo igualmente, sem distinguir nada.
    """

    permission_classes = [AllowAny]
    # Rate limiting (implementation-contract.md run
    # 20260903-1134-seo-lgpd-design-system, escopo C): endpoint público de
    # escrita explicitamente listado no contrato.
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        serializer = CadastroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # (1) Antes de TUDO, e antes de qualquer consulta ao banco: se não há
        # canal de entrega real, ninguém é criado e todo mundo recebe o mesmo
        # 503. Verificar depois da consulta ao banco transformaria a
        # configuração em oráculo de existência de conta.
        canal = verificar_canal_email()
        if not canal.disponivel:
            registrar_evento(DESTINO_CADASTRO, "sem_canal")
            logger.error(
                "cadastro: recusado por ausência de canal de entrega real (motivo=%s)",
                "; ".join(canal.motivos),
            )
            return Response(
                {"detail": DETALHE_SEM_CANAL.format(motivos="; ".join(canal.motivos))},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        email_normalizado = User.objects.normalize_email(serializer.validated_data["email"])
        existente = User.objects.filter(email__iexact=email_normalizado).first()

        if existente is not None:
            return self._responde_a_duplicado(existente)

        # Criar a conta e entregar o e-mail de verificação é UMA operação do
        # ponto de vista de quem está do outro lado: ou os dois acontecem, ou
        # nenhum. `transaction.atomic` garante isso — sem ele, uma falha do
        # provedor deixaria uma conta criada, sem e-mail, e o próximo cadastro
        # com o mesmo e-mail cairia no ramo de duplicidade acima.
        try:
            with transaction.atomic():
                usuario = serializer.save()
                enviar_email_verificacao(usuario)
        except (CanalIndisponivel, FalhaDeEntrega):
            # A exceção sai do bloco `atomic`: a transação é revertida e a
            # conta não existe. A resposta é 503, nunca 201.
            return Response(
                {"detail": DETALHE_FALHA_ENTREGA},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info("cadastro: conta criada e e-mail de verificação entregue")
        return Response({"detail": DETALHE_CADASTRO_OK}, status=status.HTTP_201_CREATED)

    def _responde_a_duplicado(self, existente) -> Response:
        """Resposta de um e-mail que JÁ tem conta — igual à de um e-mail novo.

        Reenvia a verificação só se a conta ainda não foi verificada, e nunca
        deixa a falha de envio virar diferença observável na resposta.
        """
        if not existente.email_verificado:
            try:
                enviar_email_verificacao(existente)
            except (CanalIndisponivel, FalhaDeEntrega):
                # Deliberadamente engolido NA RESPOSTA (o log e a métrica já
                # foram escritos por `identidade.emails`/`config.email_entrega`).
                # Ver a justificativa no docstring da classe.
                pass
        return Response({"detail": DETALHE_CADASTRO_OK}, status=status.HTTP_201_CREATED)


class VerificarEmailView(APIView):
    """POST /api/auth/verificar-email/ — confirmação via token (critério de aceite 2)."""

    permission_classes = [AllowAny]
    # Achado de revisão de segurança (minor): sem throttle, nada impede
    # tentativas de força bruta/enumeração do token de verificação.
    throttle_classes = [AuthSensivelAnonThrottle]

    def post(self, request):
        serializer = VerificarEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resultado = read_email_verification_token(serializer.validated_data["token"])
        if resultado is None:
            return Response(
                {"detail": "Token de verificação inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_pk, email = resultado
        try:
            user = User.objects.get(pk=user_pk, email=email)
        except (User.DoesNotExist, ValueError):
            return Response(
                {"detail": "Token de verificação inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.email_verificado = True
        user.save(update_fields=["email_verificado"])
        return Response({"detail": "E-mail verificado com sucesso."}, status=status.HTTP_200_OK)


class LoginView(APIView):
    """
    POST /api/auth/login/ — login por e-mail/senha (critério de aceite 5).

    Retorna um token de API (`rest_framework.authtoken`). Credenciais
    inválidas retornam sempre a mesma mensagem genérica, para não revelar se
    o e-mail existe ou não.
    """

    permission_classes = [AllowAny]
    # Achado de revisão de segurança (major): login não tinha NENHUM rate
    # limit — nada impedia brute force/credential stuffing contra qualquer
    # e-mail testado em volume. Ver config/throttling.py:AuthSensivelAnonThrottle.
    throttle_classes = [AuthSensivelAnonThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        senha = serializer.validated_data["senha"]

        user = authenticate(request, username=email, password=senha)
        if user is None or not user.is_active:
            return Response({"detail": MSG_CREDENCIAIS_INVALIDAS}, status=status.HTTP_401_UNAUTHORIZED)

        # `last_login` nunca era atualizado neste fluxo de login por token
        # (o helper padrão do Django só dispara em `django.contrib.auth.login`,
        # não usado aqui) — gap real encontrado ao implementar métricas de
        # usuários ativos (BRD §21, "Usuários ativos diários e mensais"),
        # que dependem deste campo para significar algo.
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "usuario": UserSerializer(user).data},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /api/auth/logout/ — invalida o token do usuário autenticado (critério de aceite 6)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"detail": "Logout realizado."}, status=status.HTTP_200_OK)


class RecuperarSenhaView(APIView):
    """
    POST /api/auth/recuperar-senha/ — inicia redefinição de senha (critério de aceite 7).

    SEMPRE responde com a mesma mensagem genérica de sucesso, exista ou não o
    e-mail, e entregue ou não. O token só é de fato gerado/enviado se o
    usuário existir.

    POR QUE A FALHA DE ENTREGA NÃO VIRA 503 AQUI (e o furo que isso fecha)
    ======================================================================
    A resposta tem de ser indistinguível entre "e-mail cadastrado" e "e-mail
    sem conta". Um 503 para o primeiro caso e 200 para o segundo seria um
    oráculo de existência de conta — trocaria um e-mail que não chega por uma
    lista de e-mails com conta, que é bem pior. Por isso a falha de entrega
    aqui NÃO muda a resposta.

    A resposta também não pode passar a mentir: `MSG_RECUPERACAO_GENERICA` é
    condicional ("Se o e-mail informado estiver cadastrado, enviaremos
    instruções"), então ela continua verdadeira mesmo quando nada foi enviado.
    Esse texto é o que fecha o furo do P0-02c neste caminho — antes ele era
    o mesmo texto, mas a mensagem de trás ("enviaremos") era uma promessa que
    o `console.EmailBackend` não podia cumprir.

    O que resta é não deixar a falha invisível: `identidade.emails` escreve
    `logger.error`, `config.email_entrega` conta em
    `portal_email_entrega_total{situacao="sem_canal"}` e o canal aparece em
    `/health-detail`. Um operador vê a falha; um atacante que enumera e-mails
    não vê diferença nenhuma.

    Eficiência de canal: a checagem vem ANTES da consulta ao banco, para não
    haver nem diferença de tempo entre os dois casos — uma consulta a mais já
    seria medível.
    """

    permission_classes = [AllowAny]
    # Achado de revisão de segurança (minor): sem throttle, cada chamada
    # dispara um `send_mail` síncrono — nada impede abuso para enviar e-mails
    # em volume ou enumerar contas por tempo de resposta.
    throttle_classes = [AuthSensivelAnonThrottle]

    def post(self, request):
        serializer = RecuperarSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        canal = verificar_canal_email()
        if not canal.disponivel:
            registrar_evento(DESTINO_REDEFINICAO, "sem_canal")
            logger.error(
                "recuperar-senha: e-mail NÃO enviado por ausência de canal de "
                "entrega real (motivo=%s)",
                "; ".join(canal.motivos),
            )
            # Resposta neutra de propósito: quem não tem conta e quem tem
            # recebem exatamente a mesma coisa. Ver o docstring da classe.
            return Response({"detail": MSG_RECUPERACAO_GENERICA}, status=status.HTTP_200_OK)

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = None

        if user is not None:
            try:
                enviar_email_redefinicao_senha(user)
            except (CanalIndisponivel, FalhaDeEntrega):
                # Mesma razão do `return` acima: a resposta não pode depender
                # de se o e-mail tem conta. O ERROR e a métrica já saíram.
                pass

        return Response({"detail": MSG_RECUPERACAO_GENERICA}, status=status.HTTP_200_OK)


class RedefinirSenhaView(APIView):
    """POST /api/auth/redefinir-senha/ — conclui a redefinição de senha (critério de aceite 7)."""

    permission_classes = [AllowAny]
    # Achado de revisão de segurança (minor): sem throttle, nada impede
    # força bruta contra o token de redefinição de senha.
    throttle_classes = [AuthSensivelAnonThrottle]

    def post(self, request):
        serializer = RedefinirSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = decode_uidb64(serializer.validated_data["uid"])

        user = None
        if uid is not None:
            try:
                user = User.objects.get(pk=uid)
            except (User.DoesNotExist, ValueError):
                user = None

        if user is None or not password_reset_token_generator.check_token(
            user, serializer.validated_data["token"]
        ):
            return Response(
                {"detail": "Token de redefinição inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["nova_senha"])
        user.save(update_fields=["password"])
        # Invalida qualquer sessão/token de API pré-existente.
        Token.objects.filter(user=user).delete()

        return Response({"detail": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)


class TrocarSenhaView(APIView):
    """POST /api/auth/trocar-senha/ — troca de senha logada (primeiro acesso
    obrigatório e troca voluntária). Exige a senha atual, define a nova e
    limpa `deve_trocar_senha`, liberando o uso normal da conta."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TrocarSenhaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["senha_atual"]):
            return Response(
                {"detail": "Senha atual incorreta."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(serializer.validated_data["nova_senha"])
        request.user.deve_trocar_senha = False
        request.user.save(update_fields=["password", "deve_trocar_senha"])
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return Response(
            {"detail": "Senha atualizada com sucesso.", "token": token.key},
            status=status.HTTP_200_OK,
        )


class GoogleLoginIniciarView(APIView):
    """
    POST /api/auth/google/iniciar/ — emite o `state`/`nonce` do login social.

    POR QUE ISTO EXISTE
    -------------------
    O login Google deste projeto não redireciona o navegador (o OAuth é
    resolvido no cliente pelo Google Identity Services e chega aqui como
    `id_token`). Sem redirect, o `state` clássico do OAuth não tem onde
    existir no protocolo — e o endpoint `POST /api/auth/google/`, anônimo
    e sem cookie de sessão lido, fica sem nenhuma proteção CSRF (o DRF só
    exige CSRF em requisição **autenticada por sessão**). Um site
    atacante poderia então forçar o navegador da vítima a fazer esse POST
    com um `id_token** que ele próprio possui e vincular a conta Google
    dele à conta da vítima: um backdoor durável, porque a vinculação fica
    no banco.

    Este endpoint fecha a porta: emite um valor aleatório de 256 bits
    guardado na sessão do navegador. Um site terceiro não consegue ler a
    resposta (CORS só libera a origem do próprio front), logo não obtém o
    nonce, logo o POST forçado é recusado. O mesmo valor tem de voltar
    assinado no claim `nonce` do `id_token`, o que também derruba o replay
    de um `id_token` capturado. Ver `identidade/oauth_google.py`.

    Resposta 503 (e não 400) quando o provedor não está configurado neste
    ambiente, para o erro de configuração não se confundir com uma
    credencial recusada.
    """

    permission_classes = [AllowAny]
    # `escrita_publica` (e não `auth_sensivel`): este endpoint não recebe
    # nem valida credencial, só emite o nonce do handshake. Cobrar o
    # orçamento de `auth_sensivel` duas vezes por login (aqui e no POST do
    # `id_token`) cortaria pela metade o número de tentativas de login que
    # o usuário legítimo tem por minuto.
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        if not oauth_google.client_id_configurado():
            oauth_google.auditar_login_google(
                desfecho="falha", motivo=oauth_google.MOTIVO_CLIENT_ID_NAO_CONFIGURADO
            )
            return Response(
                {"detail": MSG_OAUTH_NAO_CONFIGURADO},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        nonce = oauth_google.emitir_nonce(request)
        return Response(
            {"nonce": nonce, "expira_em_segundos": oauth_google.max_age_seconds()},
            status=status.HTTP_200_OK,
        )


class GoogleLoginView(APIView):
    """
    POST /api/auth/google/ — login/cadastro social via Google (critério de aceite 4).

    Recebe o `id_token` (JWT) obtido pelo cliente via Google Identity
    Services e usa `django-allauth` (`GoogleProvider.verify_token`) para
    validar a assinatura/audiência junto ao Google e extrair os dados do
    usuário. Usuário novo nasce com `papel=free` e `email_verificado=True`
    (o Google já validou o e-mail do lado dele) — ver
    `identidade/adapters.py`.

    Este fluxo NÃO é o Authorization Code flow: não há redirect para o
    Google, não há `code` para trocar, não há `redirect_uri` enviado ao
    Google e não há callback do Google aqui. O que protege a entrada é,
    nesta ordem (todas obrigatórias, nenhuma opcional):

    1. `state`/`nonce` emitido por `GoogleLoginIniciarView`, atrelado à
       sessão, de uso único e conferido contra o claim `nonce` assinado
       dentro do `id_token` (anti-CSRF e anti-replay);
    2. assinatura RS256, `iss`, `aud` e `exp` do `id_token`, conferidos
       pelo allauth contra os certificados do Google;
    3. `email_verified` verdadeiro na asserção do provedor, antes de
       qualquer vínculo de conta ou criação de usuário.

    Em teste, a verificação junto ao Google é mockada com uma chave RSA
    de teste e um `id_token` assinado localmente (nenhuma chamada de rede
    é feita, e não há credenciais reais de Google Cloud neste ambiente —
    ver task-plan.md, riscos).

    Antes de tratar o login como "usuário novo", verificamos explicitamente
    se já existe um `User` cadastrado com este e-mail (por e-mail/senha, por
    exemplo) mas ainda sem `SocialAccount` do Google vinculado — nesse caso
    associamos a conta Google ao usuário existente em vez de tentar criar um
    `User` duplicado, o que violaria a constraint `unique=True` do campo
    `email` e resultaria em `IntegrityError`/HTTP 500 (code-review-contract.md
    Finding 1).

    Para um usuário verdadeiramente novo, exigimos `aceite_termos=true` no
    payload — análogo ao que `CadastroSerializer` já exige no cadastro por
    e-mail/senha — e persistimos o consentimento LGPD (`consentimento_aceito_em`
    / `consentimento_versao_termos`) nesse momento, antes de criar a conta.
    Sem esse aceite, a conta não é criada (Finding 2).
    """

    permission_classes = [AllowAny]
    # Achado de revisão de segurança (minor): mesma lacuna de throttle das
    # demais views de autenticação.
    throttle_classes = [AuthSensivelAnonThrottle]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # (0) Provedor configurado? Sem `GOOGLE_OAUTH_CLIENT_ID` o allauth
        # usa "" como `aud` e rejeita TODOS os tokens com a mesma mensagem
        # de token inválido — um ambiente sem a variável quebra de forma
        # total e indistinguível de um ataque. 503 separa os dois casos.
        if not oauth_google.client_id_configurado():
            oauth_google.auditar_login_google(
                desfecho="falha", motivo=oauth_google.MOTIVO_CLIENT_ID_NAO_CONFIGURADO
            )
            return Response(
                {"detail": MSG_OAUTH_NAO_CONFIGURADO},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # (1) `state`/nonce: gerado por sessão, de uso único, atrelado a
        # esta sessão e não previsível. Consumido aqui — antes de qualquer
        # chamada de rede ou escrita — e conferido de novo, adiante, contra
        # o claim assinado do `id_token`.
        motivo = oauth_google.motivo_recusa_nonce(request, serializer.validated_data["nonce"])
        if motivo != oauth_google.MOTIVO_OK:
            oauth_google.auditar_login_google(desfecho="falha", motivo=motivo)
            return Response({"detail": MSG_OAUTH_NAO_CONCLUIDO}, status=status.HTTP_403_FORBIDDEN)
        nonce_esperado = serializer.validated_data["nonce"]

        # Import local para não exigir app social configurado em comandos de
        # management que não usam este endpoint.
        from allauth.socialaccount.adapter import get_adapter as get_social_adapter
        from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter

        adapter = GoogleOAuth2Adapter(request)
        provider = adapter.get_provider()

        try:
            sociallogin = provider.verify_token(
                request, {"id_token": serializer.validated_data["id_token"]}
            )
        except Exception as exc:
            # Log do TIPO da exceção, nunca do traceback: num caminho que
            # recebe a credencial, a forma mais barata de nunca vazar o
            # `id_token` em log é não logar nada que dependa do valor que
            # a biblioteca recebeu.
            oauth_google.auditar_login_google(
                desfecho="falha",
                motivo=oauth_google.MOTIVO_TOKEN_INVALIDO,
                erro_tipo=type(exc).__name__,
            )
            return Response({"detail": "Token do Google inválido."}, status=status.HTTP_400_BAD_REQUEST)

        # (2) O `nonce` assinado tem de bater com o `state` desta sessão.
        motivo = oauth_google.nonce_do_id_token_confere(sociallogin, nonce_esperado)
        if motivo != oauth_google.MOTIVO_OK:
            oauth_google.auditar_login_google(desfecho="falha", motivo=motivo)
            return Response({"detail": MSG_OAUTH_NAO_CONCLUIDO}, status=status.HTTP_403_FORBIDDEN)

        # (3) `email_verified` do provedor. Um `id_token` com
        # `email_verified: false` — que o Google emite de verdade para
        # contas de domínio ainda não verificadas pelo administrador — não
        # pode criar conta nem se vincular a uma conta local pelo e-mail:
        # isso seria sequestro de conta sem senha. A resposta é a MESMA
        # mensagem de qualquer outra recusa de identidade, para não
        # transformar o endpoint em oráculo de existência de conta.
        if not oauth_google.email_do_provider_verificado(sociallogin):
            oauth_google.auditar_login_google(
                desfecho="falha", motivo=oauth_google.MOTIVO_EMAIL_NAO_VERIFICADO
            )
            return Response({"detail": MSG_OAUTH_NAO_CONCLUIDO}, status=status.HTTP_403_FORBIDDEN)

        sociallogin.lookup()

        if sociallogin.is_existing:
            # Já existe um SocialAccount do Google vinculado a este usuário
            # (login social de retorno). O allauth só chega aqui por e-mail
            # quando o endereço veio verificado (`authenticate_by_email`
            # filtra por `verified`), então este caminho já carrega prova de
            # posse da caixa postal.
            user = sociallogin.user
            is_new = False
        else:
            # Nenhum SocialAccount vinculado ainda — mas pode já existir um
            # User com este e-mail (ex.: cadastrado por e-mail/senha
            # anteriormente). Tratar como "novo" sem essa checagem tentaria
            # criar um User duplicado (Finding 1).
            email = sociallogin.user.email
            try:
                existing_user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                existing_user = None

            if existing_user is not None:
                # PROVA DE POSSE, segunda camada. O e-mail verificado pelo
                # Google prova controle da caixa postal, mas a conta local
                # pode nunca ter confirmado esse e-mail (`email_verificado`
                # local ainda False) — ou seja, ninguém provou controle dela.
                # Não vinculamos um provedor de identidade a uma conta cujo
                # próprio e-mail continua sem confirmação: o usuário entra
                # pela senha, ou confirma o e-mail primeiro.
                if not existing_user.email_verificado:
                    oauth_google.auditar_login_google(
                        desfecho="falha",
                        motivo=oauth_google.MOTIVO_CONTA_LOCAL_NAO_VERIFICADA,
                        usuario_id=existing_user.pk,
                    )
                    return Response(
                        {"detail": MSG_OAUTH_NAO_CONCLUIDO},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                # Associa a conta Google ao usuário já existente — não cria
                # um novo User, não sobrescreve papel/consentimento já
                # persistidos.
                sociallogin.connect(request, existing_user)
                user = existing_user
                is_new = False
            else:
                # Usuário verdadeiramente novo: exige aceite explícito dos
                # termos, assim como o cadastro por e-mail/senha (Finding 2 —
                # critério de aceite 11, consentimento LGPD).
                if not serializer.validated_data.get("aceite_termos"):
                    oauth_google.auditar_login_google(desfecho="falha", motivo=oauth_google.MOTIVO_SEM_ACEITE)
                    return Response(
                        {
                            "detail": (
                                "É necessário aceitar os termos de uso e a "
                                "política de privacidade para se cadastrar."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                sociallogin.user.consentimento_aceito_em = timezone.now()
                sociallogin.user.consentimento_versao_termos = settings.TERMOS_VERSAO_ATUAL
                get_social_adapter(request).save_user(request, sociallogin)
                user = sociallogin.user
                is_new = True

        if not user.is_active:
            oauth_google.auditar_login_google(
                desfecho="falha", motivo=oauth_google.MOTIVO_CONTA_INATIVA, usuario_id=user.pk
            )
            return Response({"detail": "Conta inativa."}, status=status.HTTP_403_FORBIDDEN)

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        token, _ = Token.objects.get_or_create(user=user)
        oauth_google.auditar_login_google(
            desfecho="sucesso",
            motivo=oauth_google.MOTIVO_OK,
            usuario_id=user.pk,
            conta_nova=is_new,
        )
        return Response(
            {
                "token": token.key,
                "usuario": UserSerializer(user).data,
                "criado_agora": is_new,
            },
            status=status.HTTP_200_OK,
        )


class OnboardingView(APIView):
    """
    GET/PATCH /api/onboarding/ — captura/atualização de interesses,
    localidade e canal preferido (critérios de aceite 8 e 9).

    Exige usuário autenticado com e-mail verificado (`IsEmailVerified`) —
    decisão documentada em implementation-history.md.
    """

    permission_classes = [IsAuthenticated, IsEmailVerified]

    def get(self, request):
        return Response(OnboardingSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = OnboardingSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(OnboardingSerializer(user).data, status=status.HTTP_200_OK)


class PreferenciasCookiesView(APIView):
    """
    GET/PUT /api/preferencias-cookies/ — preferências de cookies do usuário
    AUTENTICADO (implementation-contract.md run
    20260903-1134-seo-lgpd-design-system, escopo B). Lacuna de backend
    encontrada e corrigida nesta run: endpoint não existia antes; o
    frontend precisava dele para persistir a escolha de cookies de um
    usuário logado além do localStorage (que já cobre o visitante anônimo).

    A mutação passa por `services.atualizar_preferencias_cookies` (DDD —
    view nunca escreve direto no model).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PreferenciasCookiesSerializer(request.user).data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = PreferenciasCookiesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.atualizar_preferencias_cookies(
            request.user,
            {
                "analytics": serializer.validated_data["analytics"],
                "personalizacao": serializer.validated_data["personalizacao"],
            },
        )
        return Response(PreferenciasCookiesSerializer(user).data, status=status.HTTP_200_OK)
