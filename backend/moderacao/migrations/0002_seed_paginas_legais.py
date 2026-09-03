"""
Seed das paginas legais/editoriais publicas exigidas pelo BRD (secao 17 —
governanca editorial; secao 18 — direitos autorais/LGPD/termos de uso;
secao 25 — landing page deve linkar termos). Ate esta migracao,
`PaginaEditorial` (o modelo certo, ja existente e editavel pelo admin) nao
tinha NENHUM conteudo — a tela de cadastro ja pede aceite de "termos de uso
e politica de privacidade", mas nao havia pagina nenhuma por tras do texto
"termos de uso".

NOTA: Politica de Privacidade e Politica de Cookies ja existem como paginas
estaticas Next.js (`frontend/app/privacidade/politica/`,
`frontend/app/privacidade/preferencias-cookies/`), construidas em outra
sessao (run 20260903-1134-seo-lgpd-design-system) — deliberadamente NAO
duplicadas aqui via `PaginaEditorial` para evitar duas fontes de verdade
para o mesmo documento. Este seed cobre so o que ainda faltava: Termos de
Uso e Politica Editorial.

Conteudo abaixo e um RASCUNHO FUNCIONAL, nao um documento juridico
finalizado — BRD secao 18 e explicito: "Antes do lancamento comercial,
devera existir validacao juridica especializada". Cada pagina diz isso
no proprio texto. Editavel via Django admin (moderacao.PaginaEditorial) a
qualquer momento, inclusive apos revisao juridica real.
"""

from django.db import migrations


AVISO_RASCUNHO = (
    "\n\n---\nEste texto e um rascunho funcional, gerado para permitir o "
    "funcionamento do produto antes do lancamento. Conforme a secao 18 do "
    "BRD (Direitos Autorais e Compliance), uma validacao juridica "
    "especializada e exigida antes do lancamento comercial — este conteudo "
    "deve ser revisado por um profissional antes de valer como documento "
    "legal final."
)

PAGINAS_SEED = [
    (
        "termos-de-uso",
        "Termos de Uso",
        (
            "1. Aceitacao dos termos\n"
            "Ao criar uma conta ou usar o Portal de Noticias, voce concorda com estes "
            "Termos de Uso e com a Politica de Privacidade.\n\n"
            "2. O que e o Portal de Noticias\n"
            "Uma plataforma de curadoria e inteligencia sobre noticias de terceiros: "
            "agrupamos acontecimentos cobertos por multiplas fontes, produzimos resumos "
            "proprios e indicamos sempre a fonte original. Nao somos um veiculo de "
            "imprensa que reproduz materias na integra.\n\n"
            "3. Contas de usuario\n"
            "Voce e responsavel por manter a confidencialidade da sua senha e por toda "
            "atividade realizada com sua conta. Informacoes de cadastro devem ser "
            "verdadeiras.\n\n"
            "4. Planos Free e Premium\n"
            "O plano Free inclui publicidade. O plano Premium e uma assinatura paga, "
            "com precos configuraveis pelo administrador (referencia inicial: R$20 a "
            "cada 6 meses ou R$30 a cada 12 meses), cancelavel a qualquer momento pelo "
            "usuario, sem praticas de retencao abusivas.\n\n"
            "5. Comunidade e conteudo de autores credenciados\n"
            "Publicacoes de autores credenciados sao opiniao/analise pessoal do autor, "
            "claramente identificadas como tal — nao refletem posicionamento editorial "
            "do Portal de Noticias nem endosso das opinioes expressas. Comentarios e "
            "publicacoes estao sujeitos a nossa Politica Editorial e de Moderacao.\n\n"
            "6. Uso aceitavel\n"
            "E proibido: publicar ameacas, assedio ou discurso de odio; divulgar dados "
            "pessoais de terceiros sem consentimento; enviar spam ou manipular "
            "artificialmente engajamento; violar direitos autorais de terceiros.\n\n"
            "7. Propriedade intelectual\n"
            "Resumos, agrupamentos e classificacoes produzidos pela plataforma sao de "
            "nossa titularidade. O conteudo original de cada fonte pertence a fonte "
            "respectiva — sempre linkamos e identificamos a origem.\n\n"
            "8. Encerramento de conta\n"
            "Voce pode encerrar sua conta a qualquer momento. Podemos suspender ou "
            "encerrar contas que violem estes termos, apos o devido processo descrito "
            "na Politica Editorial e de Moderacao.\n\n"
            "9. Alteracoes destes termos\n"
            "Podemos atualizar estes termos periodicamente. Mudancas relevantes serao "
            "comunicadas aos usuarios cadastrados."
            + AVISO_RASCUNHO
        ),
    ),
    (
        "politica-editorial",
        "Política Editorial",
        (
            "1. Criterios de relevancia\n"
            "Priorizamos acontecimentos com impacto ou interesse publico genuino, "
            "cobertura por multiplas fontes, e utilidade para o leitor — nunca volume "
            "ou potencial de cliques isoladamente.\n\n"
            "2. Separacao entre fato e opiniao\n"
            "Noticias do feed principal sao resumos proprios de acontecimentos "
            "reportados por veiculos de imprensa, sempre com a fonte original "
            "identificada e linkada. Publicacoes da area de Comunidade sao opiniao/"
            "analise autoral de jornalistas credenciados, claramente identificadas "
            "como tal.\n\n"
            "3. Revisao humana\n"
            "Conteudo de alta relevancia (categorias sensiveis ou cobertura por "
            "multiplas fontes) passa por fila de revisao humana antes da publicacao "
            "automatica.\n\n"
            "4. Correcao e retirada de conteudo\n"
            "Erros factuais identificados sao corrigidos assim que possivel. Qualquer "
            "pessoa pode solicitar correcao ou remocao de conteudo entrando em contato "
            "com nosso suporte.\n\n"
            "5. Credenciamento de autores\n"
            "Autores da area de Comunidade sao credenciados manualmente mediante "
            "comprovacao de formacao em Jornalismo. O credenciamento comprova o status "
            "do autor na plataforma — nao e endosso das opinioes publicadas.\n\n"
            "6. Conflitos de interesse\n"
            "Autores devem declarar conflitos de interesse relevantes ao tema sobre o "
            "qual escrevem."
            + AVISO_RASCUNHO
        ),
    ),
]


def seed_paginas(apps, schema_editor):
    PaginaEditorial = apps.get_model("moderacao", "PaginaEditorial")
    for slug, titulo, conteudo in PAGINAS_SEED:
        PaginaEditorial.objects.get_or_create(
            slug=slug, defaults={"titulo": titulo, "conteudo": conteudo}
        )


def remover_paginas(apps, schema_editor):
    PaginaEditorial = apps.get_model("moderacao", "PaginaEditorial")
    slugs = [item[0] for item in PAGINAS_SEED]
    PaginaEditorial.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("moderacao", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_paginas, remover_paginas),
    ]
