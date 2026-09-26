"""
Varredura (item 6 do P1-01b): TODO `ModelAdmin`/`InlineModelAdmin` registrado
cuja EDICAOeffective inclui um campo de texto do modelo (`CharField` com
`max_length`, ou `TextField` sem teto no banco) — ou seja, todo caminho de
escrita pelo Admin que pode levar valor acima do `varchar(N)` ou HTML cru
para o banco.

Para cada achado: model, admin, `arquivo:linha`, campos de texto realmente
editaveis com o `max_length`, e se o admin passa pela politica de
`services.limites`.

"Editavel" = o campo aparece no `base_fields` do form/formset de admin com
`disabled=False` — ou seja, o que o operador de fato consegue digitar e
salvar. Descontar nomes de `readonly_fields` nao basta: um inline pode
ainda assim esconder o resto dos campos.
"""
import inspect
import os
import sys

import django

sys.path.insert(0, "/tmp/opencode/p101b/backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_test")
django.setup()

from django.contrib import admin  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.exceptions import FieldDoesNotExist  # noqa: E402
from django.test import RequestFactory  # noqa: E402


def _request():
    """Um superuser ficticio: `get_form`/`get_formset` do Admin consultam
    `request.user` (para `has_change_permission`) mesmo sem tocar o banco."""
    User = get_user_model()
    u = User(email="varredura@exemplo.test", nome="Varredura")
    u.is_staff = True
    u.is_superuser = True
    u.is_active = True
    u.pk = 1
    req = RequestFactory().get("/admin/")
    req.user = u
    return req


def _fonte(classe):
    try:
        src = inspect.getsourcefile(classe)
    except TypeError:
        return "?"
    with open(src, encoding="utf-8") as fh:
        linhas = fh.read().splitlines()
    alvo = classe.__name__
    for n, linha in enumerate(linhas, start=1):
        if linha.strip().startswith(f"class {alvo}"):
            return f"{os.path.relpath(src, '/tmp/opencode/p101b')}:{n}"
    return os.path.relpath(src, "/tmp/opencode/p101b")


def _campos_de_texto_editaveis(model, form_class, prefixo=""):
    achados = []
    for nome in getattr(form_class, "base_fields", {}):
        campo_form = form_class.base_fields[nome]
        if campo_form.disabled:
            continue
        try:
            f = model._meta.get_field(nome)
        except FieldDoesNotExist:
            continue
        tipo = f.get_internal_type()
        if tipo == "CharField":
            achados.append((f"{prefixo}{nome}", f.max_length))
        elif tipo == "TextField":
            achados.append((f"{prefixo}{nome}", "TextField(sem teto no banco)"))
    return achados


def main():
    print("=" * 100)
    print("A) ModelAdmin: campos de TEXTO que o operador consegue DIGITAR e salvar")
    print("=" * 100)
    req = _request()
    for model, ma in sorted(
        admin.site._registry.items(), key=lambda kv: kv[0].__name__
    ):
        classe = type(ma)
        try:
            form_class = ma.get_form(req)
        except Exception as exc:  # noqa: BLE001
            print(f"!! {model.__name__}: get_form falhou: {exc}")
            continue
        texto = _campos_de_texto_editaveis(model, form_class)
        if not texto:
            continue
        # A politica pode estar na CLASSE ou herdada de um MIXIN: percorrer
        # todo o MRO, e nao so a classe, ou o mixin passa por "sem politica".
        tem_politica = False
        for base in getattr(classe, "__mro__", [classe]):
            try:
                codigo = inspect.getsource(base)
            except (TypeError, OSError):
                continue
            if "aplicar_limites" in codigo or "LimitesAdminMixin" in codigo:
                tem_politica = True
                break
        print(f"\n[{'POLITICA APLICADA' if tem_politica else 'SEM POLITICA'}] "
              f"{model.__name__} -> {classe.__name__}   ({_fonte(classe)})")
        for c, ml in texto:
            print(f"      - {c:34s} {ml}")

    print("\n" + "=" * 100)
    print("B) Inlines: campo de TEXTO editavel dentro de um inline de admin")
    print("=" * 100)
    req = _request()
    for model, ma in sorted(admin.site._registry.items(), key=lambda kv: kv[0].__name__):
        for inline_cls in getattr(ma, "inlines", []) or []:
            inline = inline_cls(model, admin.site)
            classe = type(inline)
            try:
                formset = inline.get_formset(req)
            except Exception as exc:  # noqa: BLE001
                print(f"  !! {classe.__name__}: {exc}")
                continue
            prefixo = formset.get_default_prefix()
            m2 = formset.model
            texto = _campos_de_texto_editaveis(m2, formset.form, prefixo=f"{prefixo}.")
            estado = "EDITAVEIS" if texto else "somente leitura"
            print(f"\n  {model.__name__} x {m2.__name__}  ({_fonte(classe)})  -> {estado}")
            for c, ml in texto:
                print(f"      - {c:34s} {ml}")


if __name__ == "__main__":
    main()
