import logging

from rest_framework import serializers

from .models import AcaoModeracao, Denuncia, PaginaEditorial, RecursoModeracao

logger = logging.getLogger(__name__)


class DenunciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Denuncia
        fields = [
            "id",
            "denunciante",
            "motivo",
            "detalhe",
            "content_type",
            "object_id",
            "status",
            "criado_em",
            "resolvido_em",
            "resolvido_por",
            "resolucao_motivo",
        ]
        read_only_fields = fields


class AcaoModeracaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcaoModeracao
        fields = [
            "id",
            "usuario_alvo",
            "tipo",
            "motivo",
            "aplicado_por",
            "denuncia_relacionada",
            "ativo_ate",
            "criado_em",
        ]
        read_only_fields = ["id", "aplicado_por", "criado_em"]


class RecursoModeracaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecursoModeracao
        fields = ["id", "acao", "usuario", "texto", "status", "criado_em"]
        read_only_fields = ["id", "usuario", "status", "criado_em"]


class PaginaEditorialSerializer(serializers.ModelSerializer):
    """
    `conteudo` é HTML e é renderizado por
    `frontend/app/paginas/[slug]/page.tsx` via `dangerouslySetInnerHTML`.

    Sanitizamos em DOIS pontos, de propósito:

    - `validate_conteudo` (escrita): o HTML que for gravado já é seguro.
      Registrar o valor original em `validated_data` e não sanitizado
      manteria o payload no banco, para qualquer outro consumidor futuro
      (export, API nova, admin) reintroduzir a falha.
    - `to_representation` (leitura): o banco pode conter HTML gravado
      ANTES desta validação existir, ou por um caminho que a contorne
      (admin direto, `QuerySet.update`, import). Sanitizar na leitura
      garante que a API pública nunca devolve HTML perigoso, mesmo sem
      reescrever o banco.

    Não falhar a requisição por conteúdo sujo: o admin recebe o texto
    sanitizado e um log de auditoria é emitido. Falhar fecharia o fluxo
    editorial por causa de um `<script>`; o objetivo é neutralizar, não
    punir.
    """

    class Meta:
        model = PaginaEditorial
        fields = ["slug", "titulo", "conteudo", "atualizado_em"]

    def validate_conteudo(self, valor):
        from django.core.exceptions import ValidationError

        from config.sanitizar_html import sanitizar_html

        if valor is None:
            return valor
        limpo = sanitizar_html(valor)
        if limpo != valor:
            logger.warning(
                "PaginaEditorial.conteudo sanitizado na escrita (slug=%s): "
                "HTML fora da allowlist foi removido antes de persistir.",
                self.initial_data.get("slug", "?"),
            )
        if not isinstance(limpo, str) or not limpo.strip():
            raise ValidationError(
                "O conteúdo editorial precisa ter ao menos um elemento de "
                "texto ou formatação permitido. Todo o HTML enviado foi "
                "descartado pela sanitização (ex.: só havia <script>, "
                "atributos on*, style= ou URL javascript:)."
            )
        return limpo

    def to_representation(self, instance):
        from config.sanitizar_html import sanitizar_html

        dados = super().to_representation(instance)
        # `getattr` defensivo: se o campo não vier (serialização parcial),
        # não quebramos a resposta.
        if "conteudo" in dados and isinstance(dados["conteudo"], str):
            dados["conteudo"] = sanitizar_html(dados["conteudo"])
        return dados
