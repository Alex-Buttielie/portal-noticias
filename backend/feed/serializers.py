from rest_framework import serializers


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


class FonteDetalheSerializer(serializers.Serializer):
    nome_fonte = serializers.CharField()
    url_fonte_original = serializers.URLField()
    resumo = serializers.CharField(allow_blank=True)
    # Texto integral extraído do RSS (limitado no service). O frontend exibe
    # SEMPRE truncado + crédito + link para a original (BRD secao 18).
    conteudo = serializers.CharField(allow_blank=True, required=False, default="")
    imagem_url = serializers.URLField(allow_blank=True, required=False, default="")


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
