from rest_framework import serializers

from .models import CriterioMonitoramento, MembroOrganizacao


class CriterioMonitoramentoSerializer(serializers.ModelSerializer):
    """
    Não expõe `organizacao` — o tenant é derivado do usuário autenticado
    (`services.organizacao_do_usuario`), nunca aceito do payload. Serializar o
    FK aqui publicaria o id (e permitiria o cliente tentar escrever em outra
    organização).

    `ativo` é read-only por coerência: não existe endpoint de atualização, e o
    POST só honra `tipo`/`valor` — aceitar `ativo` no input sugeriria um
    contrato que o backend não cumpre.
    """

    class Meta:
        model = CriterioMonitoramento
        fields = ["id", "tipo", "valor", "ativo", "criado_em"]
        read_only_fields = ["id", "ativo", "criado_em"]


class MembroOrganizacaoSerializer(serializers.ModelSerializer):
    """
    Não expõe `organizacao` (mesmo motivo acima) nem o id do usuário. Só o
    e-mail do membro da PRÓPRIA organização, derivado de `organizacao.membros`
    na view.
    """

    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = MembroOrganizacao
        fields = ["id", "email", "papel_na_organizacao", "criado_em"]
        read_only_fields = ["id", "email", "criado_em"]
