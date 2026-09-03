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

    def populate_user(self, request, sociallogin, data):
        user = sociallogin.user
        email = data.get("email") or ""
        nome = data.get("name") or " ".join(
            part for part in [data.get("first_name"), data.get("last_name")] if part
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
