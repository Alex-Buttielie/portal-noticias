from django.db import models
from django.utils import timezone


class Patrocinio(models.Model):
    """
    M-10 (run 20261012-1806-monetizacao-sprint1) — patrocínio identificado,
    receita direta sem depender de conta de AdSense nem de consentimento de
    anúncio (BRD §5 e §17). Mecanismo apenas: preço/tabela comercial real
    fica fora do código (ver implementation-contract.md, não-objetivos).

    `posicao` é texto livre (igual a `AdsSlot`'s `id`/posição), não um enum
    fechado — cada ponto de montagem (`PatrocinioSlot`) escolhe a posição
    que faz sentido (ex. "newsletter", "radar", "home-topo") sem exigir
    alteração de código aqui para uma posição nova.
    """

    anunciante = models.CharField(max_length=150)
    # URL do criativo (imagem) a ser exibido — nunca hospedado neste
    # repositório; sempre uma URL fornecida por quem cadastra.
    criativo_url = models.URLField(max_length=1000)
    # Texto alternativo da imagem, OBRIGATÓRIO: `PatrocinioSlot` (frontend)
    # exige `alt` real, nunca inventado/genérico — quem cadastra escreve.
    texto_alt = models.CharField(max_length=200)
    url = models.URLField(max_length=1000, help_text="Destino do clique. O frontend abre com rel=sponsored nofollow noopener.")
    posicao = models.CharField(max_length=60, db_index=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "patrocínio"
        verbose_name_plural = "patrocínios"
        ordering = ["-data_inicio"]
        indexes = [
            models.Index(fields=["posicao", "ativo"]),
        ]

    def __str__(self):
        return f"{self.anunciante} ({self.posicao}, {self.data_inicio} a {self.data_fim})"

    def esta_vigente(self, hoje=None) -> bool:
        """`ativo=True` E a data de hoje dentro de [data_inicio, data_fim]."""
        hoje = hoje or timezone.localdate()
        return bool(self.ativo and self.data_inicio <= hoje <= self.data_fim)

    @classmethod
    def vigente_para_posicao(cls, posicao: str, hoje=None):
        """Patrocínio ativo e dentro do período para `posicao`, ou `None`.

        Critério de desempate (mais de um patrocínio vigente na mesma
        posição, ex. troca programada): o de `data_inicio` mais recente
        primeiro (`Meta.ordering`), ou seja, o patrocínio que começou por
        último é o exibido — o cadastro mais recente vence.
        """
        hoje = hoje or timezone.localdate()
        return (
            cls.objects.filter(
                posicao=posicao,
                ativo=True,
                data_inicio__lte=hoje,
                data_fim__gte=hoje,
            )
            .order_by("-data_inicio", "-criado_em")
            .first()
        )
