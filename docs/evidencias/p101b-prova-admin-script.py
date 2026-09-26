"""
Prova medida P1-01b: o caminho de escrita pelo Admin do Django aceita e
persiste `NewsItem.titulo` (e `NewsCluster.titulo_acontecimento`) com
`</script>` byte-identico, porque `NewsItemAdmin.save_model` nao aplica a
politica de `catalogo_noticias.services.limites`.

Roda um POST REAL de changeform pelo admin (session+login), com `follow=False`
para inspecionar o redirect e reler o objeto do banco.

Uso: python prova_admin_script.py [antes|depois]
"""
import os
import sys

import django

sys.path.insert(0, "/tmp/opencode/p101b/backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from catalogo_noticias.models import NewsCluster, NewsItem  # noqa: E402

User = get_user_model()

TITULO_MALICIOSO = (
    "Prefeitura anuncia obra </script><script>alert('XSS-ARMADO')</script>"
)
CLUSTER_MALICIOSO = "Vazamento emacapetuba </script><img src=x onerror=alert(1)>"

# Um valor acima do `max_length` do modelo (titulo = varchar(300)).
TITULO_LONGO = "T" * 420
# Acima do `max_length` de `url_fonte_original` (varchar(1000)).
URL_LONGA = "https://fonte-externa.test/noticia/" + ("segmento/" * 130)


def _erros_do_form(response):
    """Extrai os erros de formulario do HTML reapresentado pelo Admin."""
    import re

    if response.status_code != 200:
        return "(sem erros: resposta nao reapresentou o form)"
    ctx = getattr(response, "context", None)
    if isinstance(ctx, dict) and "adminform" in ctx:
        try:
            erros = ctx["adminform"].form.errors
            return {k: list(v) for k, v in erros.items()}
        except Exception:
            pass
    html = response.content.decode("utf-8", "replace")
    achados = re.findall(r'class="errorlist"[^>]*>(.*?)</ul>', html, re.S)
    return [re.sub(r"<[^>]+>", " ", a).strip() for a in achados] or "(vazio)"


EMAIL_ADMIN = "admin_p101b@exemplo.test"
SENHA = "SenhaDeTesteP101b-2026"


def _superuser():
    u, _ = User.objects.get_or_create(
        email=EMAIL_ADMIN, defaults={"nome": "Admin P1-01b", "is_staff": True}
    )
    u.nome = "Admin P1-01b"
    u.is_staff = True
    u.is_superuser = True
    u.is_active = True
    u.papel = "admin"
    u.set_password(SENHA)
    u.save()
    return u


def _login():
    c = Client()
    assert c.login(username=EMAIL_ADMIN, password=SENHA), "login falhou"
    return c


def _criar_item_via_admin(c, titulo, url):
    dados = {
        "titulo": titulo,
        "resumo_proprio": "Resumo de teste.",
        "conteudo_bruto": "",
        "conteudo_completo": "",
        "url_fonte_original": url,
        "nome_fonte": "Fonte de Teste",
        "categoria": "cidades",
        "autor": "",
        "pais": "",
        "estado": "",
        "cidade": "",
        "imagem_url": "",
        "timestamp_publicacao_fonte_0": "",
        "timestamp_publicacao_fonte_1": "",
        "status_revisao": NewsItem.STATUS_PENDENTE,
        "urgente": "on",
        "cluster": "",
        "tags": "[]",
    }
    r = c.post(reverse("admin:catalogo_noticias_newsitem_add"), dados)
    return r


def _criar_cluster_via_admin(c, titulo):
    dados = {
        "titulo_acontecimento": titulo,
        "categoria_dominante": "cidades",
        # O Admin de cluster tem um inline (NewsItemInline): sem o formset de
        # gerenciamento o POST e recusado com 400 e nada e salvo.
        "numero_fontes_distintas": "1",
        "itens-TOTAL_FORMS": "0",
        "itens-INITIAL_FORMS": "0",
        "itens-MIN_NUM_FORMS": "0",
        "itens-MAX_NUM_FORMS": "1000",
    }
    return c.post(reverse("admin:catalogo_noticias_newscluster_add"), dados)


def main():
    _superuser()
    c = _login()
    relatorio = []

    # --- 1. titulo com </script> via Admin -----------------------------------
    url = "https://fonte-externa.test/p101b-script-injetado"
    r = _criar_item_via_admin(c, TITULO_MALICIOSO, url)
    item = NewsItem.objects.filter(url_fonte_original=url).first()
    relatorio.append(("item </script> — HTTP", r.status_code))
    relatorio.append(
        ("item </script> — persistiu byte-identico", bool(item) and item.titulo == TITULO_MALICIOSO)
    )
    relatorio.append(
        ("item </script> — tem '</script>' no banco", bool(item) and "</script>" in item.titulo)
    )
    if item:
        relatorio.append(("item </script> — titulo lido do banco", repr(item.titulo)))

    # --- 2. cluster com </script> via Admin ---------------------------------
    r2 = _criar_cluster_via_admin(c, CLUSTER_MALICIOSO)
    # Busca pelo MAIS RECENTE: antes da correcao o titulo voltava byte-identico
    # e o filtro por `titulo_acontecimento` encontrava; depois da correcao o
    # titulo gravado e o texto saneado, entao o filtro por titulo nao acha.
    cluster = NewsCluster.objects.order_by("-pk").first()
    relatorio.append(("cluster </script> — HTTP", r2.status_code))
    relatorio.append(
        (
            "cluster </script> — persistiu byte-identico",
            bool(cluster) and cluster.titulo_acontecimento == CLUSTER_MALICIOSO,
        )
    )
    relatorio.append(("cluster </script> — erros do form", _erros_do_form(r2)))
    if cluster:
        relatorio.append(
            ("cluster </script> — titulo lido do banco", repr(cluster.titulo_acontecimento))
        )

    # --- 3. titulo acima do limite (varchar(300)) ---------------------------
    url3 = "https://fonte-externa.test/p101b-acima-do-limite"
    try:
        r3 = _criar_item_via_admin(c, TITULO_LONGO, url3)
        item3 = NewsItem.objects.filter(url_fonte_original=url3).first()
        relatorio.append(("titulo longo — HTTP", r3.status_code))
        relatorio.append(
            ("titulo longo — persistiu", bool(item3))
        )
        if item3:
            relatorio.append(("titulo longo — tamanho no banco", len(item3.titulo)))
    except Exception as exc:  # DataError do Postgres = o que o Admin devolve
        relatorio.append(("titulo longo — EXCECAO", f"{type(exc).__name__}: {exc}"))
    relatorio.append(("titulo longo — erros do form", _erros_do_form(r3) if "r3" in dir() else "?"))

    # --- 4. url_fonte_original acima do limite (varchar(1000)) --------------
    url4 = "https://fonte-externa.test/p101b-url-acima-do-limite"
    try:
        r4 = _criar_item_via_admin(c, "Titulo normal", URL_LONGA)
        item4 = NewsItem.objects.filter(url_fonte_original=URL_LONGA).first()
        relatorio.append(("url longa — tamanho enviado", len(URL_LONGA)))
        relatorio.append(("url longa — HTTP", r4.status_code))
        relatorio.append(("url longa — a URL inteira foi preservada", bool(item4) and item4.url_fonte_original == URL_LONGA))
    except Exception as exc:
        relatorio.append(("url longa — EXCECAO", f"{type(exc).__name__}: {exc}"))
    relatorio.append(("url longa — erros do form", _erros_do_form(r4) if "r4" in dir() else "?"))

    # --- 5. idempotencia: salvar duas vezes o MESMO titulo ----------------
    if item:
        url5 = "https://fonte-externa.test/p101b-idem"
        _criar_item_via_admin(c, TITULO_MALICIOSO, url5)
        i5 = NewsItem.objects.filter(url_fonte_original=url5).first()
        if i5:
            antes = i5.titulo
            form_url = reverse("admin:catalogo_noticias_newsitem_change", args=[i5.pk])
            dados = {
                "titulo": antes,
                "resumo_proprio": "",
                "conteudo_bruto": "",
                "conteudo_completo": "",
                "url_fonte_original": url5,
                "nome_fonte": "Fonte de Teste",
                "categoria": "",
                "autor": "",
                "pais": "",
                "estado": "",
                "cidade": "",
                "imagem_url": "",
                "timestamp_publicacao_fonte_0": "",
                "timestamp_publicacao_fonte_1": "",
                "status_revisao": NewsItem.STATUS_APROVADO,
                "cluster": "",
                "tags": "[]",
            }
            c.post(form_url, dados)
            i5.refresh_from_db()
            relatorio.append(
                ("idempotencia 2o save — titulo inalterado", i5.titulo == antes)
            )
            relatorio.append(("idempotencia 2o save — titulo", repr(i5.titulo)))
            relatorio.append(
                ("idempotencia 2o save — status alterado", i5.status_revisao == NewsItem.STATUS_APROVADO)
            )

    # --- limpeza ------------------------------------------------------------
    NewsItem.objects.filter(url_fonte_original__contains="fonte-externa.test/p101b").delete()
    NewsCluster.objects.filter(titulo_acontecimento=CLUSTER_MALICIOSO).delete()

    print("=" * 78)
    for k, v in relatorio:
        print(f"{k:52s} | {v}")
    print("=" * 78)


if __name__ == "__main__":
    main()
