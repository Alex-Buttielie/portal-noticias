from rest_framework import serializers


# H-07 (run 20261013-1048-home-radar-central-ux): campo booleano calculado
# em `feed/services.py` (NÃO aqui) a partir de
# `catalogo_noticias.providers.fallback_local.origem_fallback_local`, sobre
# `NewsItem.tags` do item representante — nunca inventado, nunca derivado
# de comparação de string com o texto fixo (que poderia divergir se o texto
# mudar). `default=False`: dados antigos/dicts que não passaram pelo cálculo
# (ex. outros callers de teste) continuam válidos sem o campo.
_AJUDA_RESUMO_E_FALLBACK = (
    "True quando o resumo exibido é o texto fixo gerado pelo fallback local "
    "(sem resumo editorial) — usado pelo frontend para mostrar o aviso no "
    "máximo uma vez por página, em vez de repeti-lo em cada ocorrência do "
    "resumo (lead, preview truncado, lista por fonte)."
)


class FeedEntrySerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    resumo = serializers.CharField(allow_blank=True)
    categoria = serializers.CharField(allow_blank=True)
    urgente = serializers.BooleanField()
    numero_fontes = serializers.IntegerField()
    timestamp = serializers.DateTimeField()
    imagem_url = serializers.URLField(allow_blank=True, required=False, default="")
    # Localidade best-effort do NewsItem (nunca inventada — vazia quando
    # o pipeline de ingestão não inferiu). Exposta para a Home exibir
    # "cidade/UF, estado, país" só quando existir no dado.
    pais = serializers.CharField(allow_blank=True, required=False, default="")
    estado = serializers.CharField(allow_blank=True, required=False, default="")
    cidade = serializers.CharField(allow_blank=True, required=False, default="")
    # Nome da fonte representante (rastreabilidade BRD seção 18). O frontend
    # exibe como "Fonte: X" — nunca inventa autor/colunista.
    nome_fonte = serializers.CharField(allow_blank=True, required=False, default="")
    # FRENTE 3 — autor/colunista creditado no RSS (best-effort, vazio quando
    # não informado). O frontend prefere este campo a nome_fonte na linha
    # de autoria e nunca o inventa.
    autor = serializers.CharField(allow_blank=True, required=False, default="")
    # FRENTE 6 — selo forçado pela Central (RegraCuradoria selo_forcado/
    # exclusivo_forcado). Vazio = sem override; o frontend mantém a regra
    # local de derivar selo do dado quando vazio.
    selo_editorial = serializers.CharField(allow_blank=True, required=False, default="")
    # H-07 — ver `_AJUDA_RESUMO_E_FALLBACK` acima.
    resumo_e_fallback = serializers.BooleanField(required=False, default=False, help_text=_AJUDA_RESUMO_E_FALLBACK)


class FonteDetalheSerializer(serializers.Serializer):
    nome_fonte = serializers.CharField()
    url_fonte_original = serializers.URLField()
    resumo = serializers.CharField(allow_blank=True)
    # Texto integral extraído do RSS (limitado no service). O frontend exibe
    # SEMPRE truncado + crédito + link para a original (BRD secao 18).
    conteudo = serializers.CharField(allow_blank=True, required=False, default="")
    imagem_url = serializers.URLField(allow_blank=True, required=False, default="")
    # H-07 — ver `_AJUDA_RESUMO_E_FALLBACK` acima.
    resumo_e_fallback = serializers.BooleanField(required=False, default=False, help_text=_AJUDA_RESUMO_E_FALLBACK)


class FeedDetalheSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    categoria = serializers.CharField(allow_blank=True)
    urgente = serializers.BooleanField()
    timestamp = serializers.DateTimeField()
    pais = serializers.CharField(allow_blank=True, required=False, default="")
    estado = serializers.CharField(allow_blank=True, required=False, default="")
    cidade = serializers.CharField(allow_blank=True, required=False, default="")
    fontes = FonteDetalheSerializer(many=True)


# FRENTE 3 — recomendação/busca/cobertura (só leitura/cálculo; sem regra na UI).
class SecaoHomeSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    resumo = serializers.CharField(allow_blank=True, required=False, default="")
    categoria = serializers.CharField(allow_blank=True, required=False, default="")
    urgente = serializers.BooleanField(required=False, default=False)
    numero_fontes = serializers.IntegerField(required=False, default=1)
    timestamp = serializers.DateTimeField()
    imagem_url = serializers.URLField(allow_blank=True, required=False, default="")
    pais = serializers.CharField(allow_blank=True, required=False, default="")
    estado = serializers.CharField(allow_blank=True, required=False, default="")
    cidade = serializers.CharField(allow_blank=True, required=False, default="")
    nome_fonte = serializers.CharField(allow_blank=True, required=False, default="")
    score = serializers.FloatField(required=False, default=0.0)
    motivo = serializers.CharField(allow_blank=True, required=False, default="")
    override = serializers.CharField(allow_blank=True, required=False, default=None)
    # H-07 — ver `_AJUDA_RESUMO_E_FALLBACK` acima.
    resumo_e_fallback = serializers.BooleanField(required=False, default=False, help_text=_AJUDA_RESUMO_E_FALLBACK)


class ResultadoBuscaSerializer(SecaoHomeSerializer):
    relevancia = serializers.FloatField(required=False, default=0.0)
    trecho = serializers.CharField(allow_blank=True, required=False, default="")


class AtualizacaoCoberturaSerializer(serializers.Serializer):
    nome_fonte = serializers.CharField()
    url_fonte_original = serializers.URLField()
    titulo = serializers.CharField()
    timestamp = serializers.DateTimeField()


class CoberturaCompletaSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=["cluster", "item"])
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    categoria = serializers.CharField(allow_blank=True, required=False, default="")
    urgente = serializers.BooleanField(required=False, default=False)
    timestamp = serializers.DateTimeField()
    total_atualizacoes = serializers.IntegerField()
    numero_fontes = serializers.IntegerField()
    atualizacoes = AtualizacaoCoberturaSerializer(many=True)
    relacionadas = ResultadoBuscaSerializer(many=True)
    fontes = FonteDetalheSerializer(many=True)
