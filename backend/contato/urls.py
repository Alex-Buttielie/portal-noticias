"""Rotas do formulário de contato (P1-15b).

A URL canônica é `POST /api/contato/` (montada em `config/urls.py:14-31`) — a
mesma que o diagnóstico do P1-15 sondou e encontrou em 404, e a que o frontend
vai usar quando `ContatoForm.tsx` trocar o bloco "sem canal" por
`await api.<novaFuncao>(...)` (`frontend/lib/api.ts`). Barra final é
obrigatória: é o que faz o `reverse()` do Django devolver a URL canônica, e o
frontend sempre manda a barra (os outros endpoints do projeto, `inscrever/`,
`lista-espera/`, seguem a mesma convenção).
"""

from django.urls import path

from . import views

app_name = "contato"

urlpatterns = [
    path("", views.ContatoView.as_view(), name="enviar"),
]
