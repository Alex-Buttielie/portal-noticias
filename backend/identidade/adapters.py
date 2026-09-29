from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adapter customizado do django-allauth para o `User` do módulo
    identidade/.

    O `User` deste projeto não tem campos `username`/`first_name`/
    `last_name` (usa `email` como identificador único e `nome` como nome
    completo), então os defaults do allauth (pensados para
    `AbstractUser`-like) não populam o cadastro corretamente — este adapter
    ajusta isso e aplica as regras de negócio do critério de aceite 4 do
    implementation-contract.md: usuário novo via Google nasce com
    `papel=free`; e-mail já é considerado verificado (o Google já validou o
    e-mail do lado dele).
    """

    def authenticate_by_email(self, sociallogin):
        """
        NUNCA autentica/vincula por e-mail sozinho — devolve sempre `None`.

        O default do allauth (`DefaultSocialAccountAdapter.authenticate_by_email`)
        procura um `User` local pelo e-mail do provedor e, se achar, faz
        `SocialLogin.lookup()` já consider o login como "de usuário
        existente" (`sociallogin.is_existing == True`). Isso带来 dois
        problemas neste projeto, e por isso é desligado aqui:

        1. **Auditoria.** O auto-vínculo acontece dentro da biblioteca, sem
           passar por `GoogleLoginView`, logo sem o log de auditoria de
           `identidade.oauth_google` e sem o motivo da decisão. Todo
           vínculo por e-mail precisa ficar num único lugar, com rastro.
        2. **Prova de posse em duas camadas.** A decisão de vincular uma
           conta Google a uma conta local **já existente** é uma decisão de
           segurança (é o caminho de sequestro de conta: quem controla um
           e-mail controla a conta). Ela depende de duas coisas — o
           provedor ter verificado o e-mail **e** a conta local já ter
           confirmado o próprio e-mail. O default do allauth só olha a
           primeira. Concentrar a decisão em `GoogleLoginView` deixa as
           duas camadas explícitas e testáveis.

        O efeito colateral é que `sociallogin.lookup()` só resolve por
        `SocialAccount(uid)` — o login de retorno de quem já está
        vinculado continua funcionando, e todo o resto cai no caminho
        explícito da view (inclusive a associação de quem já tinha conta
        por e-mail/senha).
        """
        return None

    def populate_user(self, request, sociallogin, data):
        user = sociallogin.user
        email = data.get("email") or ""
        # O claim `name` do Google ("Maria Silva") NÃO chega em `data`:
        # `GoogleProvider.extract_common_fields` monta só `email`,
        # `first_name` (`given_name`) e `last_name` (`family_name`) — e o
        # id_token do Google não traz `family_name` na prática, então o
        # fallback por concatenação abaixo cortava o sobrenome e o usuário
        # ficava com "Maria" em vez de "Maria Silva". O payload verificado
        # está inteiro em `sociallogin.account.extra_data`, então é de lá
        # que o nome completo vem.
        extra_data = getattr(sociallogin.account, "extra_data", None) or {}
        nome = (
            data.get("name")
            or extra_data.get("name")
            or " ".join(
                part for part in [data.get("first_name"), data.get("last_name")] if part
            )
        )
        user.email = email
        user.nome = nome or user.nome
        return user

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        user.set_unusable_password()
        if not user.pk:
            user.papel = user.papel or user.PAPEL_FREE
            user.email_verificado = True
            # Consentimento LGPD (`consentimento_aceito_em` /
            # `consentimento_versao_termos`): `GoogleLoginView.post` já
            # validou o aceite explícito dos termos (`aceite_termos=true` no
            # payload) e preencheu esses dois campos em `sociallogin.user`
            # ANTES de chamar `save_user` — só chegamos aqui para um usuário
            # verdadeiramente novo depois dessa validação (ver
            # code-review-contract.md Finding 2 e implementation-history.md).
            # Este adapter não precisa (nem deve) decidir isso sozinho, pois
            # não tem acesso direto ao payload da requisição.
        sociallogin.save(request)
        return user
