"""
Carga de usuário inicial (ex.: dono/admin em produção).

Cria ou atualiza um usuário com senha inicial e `deve_trocar_senha=True`,
forçando a troca no primeiro login (`POST /api/auth/trocar-senha/`).

Há DOIS caminhos, e a diferença é de onde nasce a senha:

1. Com senha (comportamento original, intocado): a senha vem de `--password`,
   de `PROD_SEED_PASSWORD` ou do prompt interativo, é validada, é gravada e o
   `Token` anterior é invalidado. É o que `subir-localhost.sh` /
   `subir-localhost.bat` usam, e continua igual.

2. Com `--sem-senha`: a conta nasce com `set_unusable_password()` — a senha
   NÃO EXISTE em lugar nenhum (nem no argv, nem no ambiente, nem no banco, nem
   no log). O primeiro acesso é o fluxo de recuperação de senha que o produto
   já tem (`/recuperar-senha` → `POST /api/auth/recuperar-senha/` →
   `/redefinir-senha` → `POST /api/auth/redefinir-senha/`), e o primeiro login
   ainda pede a troca de senha porque `deve_trocar_senha=True`. É o caminho
   usado pelo gate `usuarios_teste` do `deploy.yml` em DEV/HOMOLOG.

   `check_password` nunca casa com uma senha inutilizável, então nenhum login
   abre porta sem passar por uma senha que a própria pessoa definiu.

   ESTE CAMINHO É IDEMPOTENTE: num redeploy, se a conta já tem senha
   utilizável (porque alguém já passou pela recuperação), a senha e a flag
   `deve_trocar_senha` são PRESERVADAS em vez de reescritas. Ver `handle()`.

Uso (na VPS, via compose):
    docker compose --env-file .env.production exec web python manage.py \\
        criar_usuario_carga --email buttielle3@gmail.com --superuser
    # a senha é lida de PROD_SEED_PASSWORD (nunca via argumento/terminal
    # com histórico) ou digitada interativamente.

    # conta de teste de DEV/HOMOLOG: sem senha em lugar nenhum
    python manage.py criar_usuario_carga \\
        --email teste-free@dev.portal-noticias.com.br --sem-senha --papel free

Variáveis de ambiente:
    PROD_SEED_EMAIL / PROD_SEED_PASSWORD — valores padrão quando os
    argumentos --email/--password não são passados. `--sem-senha` ignora
    `PROD_SEED_PASSWORD` (avisa, não falha: a ambiguidade que é preciso
    recusar é a de `--password` digitado por alguém).
"""

from __future__ import annotations

import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Cria/atualiza usuário de carga com troca de senha obrigatória no primeiro login. "
        "Com --sem-senha a conta nasce sem senha utilizável e o primeiro acesso é pelo "
        "fluxo de recuperação de senha."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", default=os.environ.get("PROD_SEED_EMAIL", ""))
        parser.add_argument(
            "--password",
            # `default=None` (e não o valor do ambiente) é o que permite distinguir
            # "--password X" digitado por alguém de `PROD_SEED_PASSWORD` herdado do
            # ambiente. `--sem-senha` precisa dessa distinção para recusar SÓ a
            # ambiguidade que é de fato ambígua; o valor do ambiente é apenas
            # ignorado, com aviso. O caminho legado é idêntico ao de antes: sem
            # argumento, sem variável e sem prompt, continua pedindo a senha.
            default=None,
            help="Senha inicial (prefira PROD_SEED_PASSWORD; será pedida interativamente se vazia).",
        )
        parser.add_argument("--nome", default="")
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Torna staff+superuser (acesso ao /admin e à Central).",
        )
        parser.add_argument(
            "--papel",
            default="admin",
            choices=["free", "premium", "admin"],
            help="Papel no portal (default: admin).",
        )
        parser.add_argument(
            "--sem-senha",
            action="store_true",
            help=(
                "Cria/atualiza a conta SEM senha utilizável: a senha não existe em "
                "lugar nenhum e o primeiro acesso é por /recuperar-senha. "
                "Incompatível com --password."
            ),
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip()
        if not email:
            raise CommandError("Informe --email ou PROD_SEED_EMAIL.")
        email = User.objects.normalize_email(email)
        sem_senha = options["sem_senha"]
        senha_explicita = options["password"] is not None
        password = options["password"] if senha_explicita else (os.environ.get("PROD_SEED_PASSWORD") or "")

        if sem_senha and senha_explicita:
            # Nunca escolher um dos dois em silêncio: quem chamou pediu as duas
            # coisas, e cada uma tem uma consequência de segurança diferente.
            raise CommandError(
                "--sem-senha e --password são mutuamente exclusivos: --sem-senha diz "
                "que a senha não existe (primeiro acesso por /recuperar-senha) e "
                "--password diz que ela existe. Escolha um dos dois."
            )
        if sem_senha and password:
            # O ambiente trouxe PROD_SEED_PASSWORD, mas a chamada foi explícita
            # por --sem-senha — não é ambiguidade, é precedência. Falhar aqui
            # deixaria o gate de DEV/HOMOLOG refém de uma variável que o
            # workflow não controla; e o prompt `getpass` jamais pode rodar
            # neste caminho (no deploy não há terminal), então o comando
            # perguntaria e esperaria para sempre.
            self.stdout.write(
                self.style.WARNING(
                    "AVISO: PROD_SEED_PASSWORD está no ambiente e foi IGNORADA porque "
                    "--sem-senha foi pedido; esta conta não terá senha."
                )
            )

        if not sem_senha:
            if not password:
                password = getpass.getpass("Senha inicial: ")
            try:
                validate_password(password)
            except ValidationError as exc:
                raise CommandError(f"Senha inicial inválida: {'; '.join(exc.messages)}")

        user, criado = User.objects.get_or_create(
            email__iexact=email,
            defaults={"email": email},
        )
        user.email = email
        if options["nome"]:
            user.nome = options["nome"]
        user.papel = options["papel"]
        user.is_active = True
        user.email_verificado = True

        from rest_framework.authtoken.models import Token

        # ORDEM IMPORTA (critério 2 do implementation-contract.md): primeiro se
        # pergunta se a conta JÁ tem senha utilizável, e só depois se decide se
        # escreve alguma coisa. `set_unusable_password()` aplicado cegamente a
        # cada deploy apagaria a senha que a pessoa definiu na recuperação e
        # trancaria fora quem já tinha acesso — o gate roda a cada push, então
        # isso não é um caso raro, é o caminho comum.
        #
        # Só o que é DERIVADO da flag entra no estado de primeiro acesso: papel,
        # is_active e email_verificado continuam sendo normalizados a cada
        # deploy, porque corrigir drift administrativo é o propósito de
        # "criar ou atualizar" e nenhuma dessas escritas é destrutiva.
        if sem_senha:
            preserva_senha = not criado and user.has_usable_password()
            if not preserva_senha:
                user.set_unusable_password()
                user.deve_trocar_senha = True
        else:
            preserva_senha = False
            user.deve_trocar_senha = True
            user.set_password(password)
        if options["superuser"]:
            user.is_staff = True
            user.is_superuser = True
        user.save()
        # Tokens antigos não valem nada com a senha nova. A ressalva é o caminho
        # `--sem-senha` que PRESERVOU a senha: como a credencial continua
        # valendo, derrubar o token só deslogaria quem estava usando o ambiente
        # de teste, sem nenhum ganho de segurança.
        if not sem_senha or not preserva_senha:
            Token.objects.filter(user=user).delete()

        acao = "criado" if criado else "atualizado"
        if sem_senha:
            resumo = (
                "sem senha utilizável; o primeiro acesso é por /recuperar-senha com este e-mail"
                if not preserva_senha
                else "senha já definida foi preservada (o primeiro acesso já aconteceu)"
            )
        else:
            resumo = "troca de senha exigida no primeiro login"
        self.stdout.write(
            self.style.SUCCESS(
                f"Usuário {email} {acao} (papel={user.papel}, "
                f"superuser={user.is_superuser}) — {resumo}."
            )
        )
