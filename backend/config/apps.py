"""
AppConfig do pacote `config` (o próprio projeto Django).

Só existe por causa do `MAJOR-1` (Onda 2): o `ready()` registra um system
check que transforma uma configuração inválida de `TRUSTED_PROXY_IPS` em
erro de `manage.py check`, visível no deploy.

Por que precisa disso, e por que um `system check` e não um `raise` no boot
do módulo: uma entrada não interpretável (ex.: o intervalo de IP digitado
com um caractere a mais) é DESCARTADA por `config.proxies` — de propósito,
para que um erro de digitação não derrube o processo no meio do tráfego.
Só que o efeito de descartar é silencioso e vai na direção perigosa: aquele
proxy deixa de contar como confiável, o `X-Forwarded-For` que ele escreve
volta a ser ignorado, e todo o tráfego atrás dele volta a ser limitado pelo
IP do proxy — mais restritivo, não menos, mas invisível para quem opera.
`raise` no import seria o extremo oposto e tiraria o sistema do ar por um
erro de configuração; o `check` mantém o processo no ar e leva o problema
até o pipeline.

`config` entra em `INSTALLED_APPS` (settings.py:254) justamente para que
`config/management/commands/` seja descoberto; este AppConfig não muda nada
disso — só dá um lugar canônico para o registro do check.
"""

from django.apps import AppConfig
from django.core.checks import Error, register


class ConfigAppConfig(AppConfig):
    name = "config"
    verbose_name = "Configuração do projeto"

    def ready(self) -> None:
        register(self._check_proxies_confiados)

    @staticmethod
    def _check_proxies_confiados(app_configs, **kwargs):
        """Erro de `check` quando `TRUSTED_PROXY_IPS` tem entrada inválida.

        Deliberadamente NÃO é Warning: um proxy declarado com erro de
        digitação significa que o limite por IP de quem vem por trás dele
        passou a ser o do próprio proxy, o que em `10/min` no login
        (`config/throttling.py`) derruba o acesso de todos os usuários
        legítimos que passam por ali. Falhar no `check` é o que impede esse
        deploy de parecer saudável.
        """
        from config.proxies import _falhar_se_configuracao_invalida

        try:
            _falhar_se_configuracao_invalida()
        except Exception as exc:  # noqa: BLE001 — o check reporta, não levanta
            return [
                Error(
                    str(exc),
                    id="config.E001",
                    hint=(
                        "TRUSTED_PROXY_IPS aceita IPs e prefixos CIDR separados "
                        "por vírgula, ex.: 127.0.0.1 ou 10.0.0.0/8. Entrada "
                        "inválida é descartada e o proxy correspondente deixa de "
                        "ser considerado confiável."
                    ),
                )
            ]
        return []
