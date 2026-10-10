#!/bin/bash
# Reaplica as regras de firewall do HOST que o Docker apaga.
#
# POR QUE ESTE SCRIPT EXISTE (medido em 2026-10-08): nao havia NENHUM hook de
# boot. As 5 regras do DOCKER-USER (4300, 4200, 4100, 3306, 3000) e o DROP das
# portas 8080/8443 estavam vivas apenas enquanto o Docker nao reiniciasse. Um
# reboot, um `docker restart` ou um `docker compose down/up` abria tudo de novo,
# sem ninguem ver. Isso e a forma classica de um controle que everybody acha que
# esta no lugar.
#
# POR QUE 8080/8443 NAO VAO NO DOCKER-USER: o Docker faz DNAT na cadeia
# `nat`/`PREROUTING` (dport 8080 -> 172.22.0.6:80). Quando o pacote chega em
# `filter`/`forward`, a porta de destino JA e 80/443. Uma regra em DOCKER-USER
# casando `dport 8080` nunca casa — e foi exatamente o que se mediu: regra
# inserida, contador em 0 pacotes, e a porta continuava servindo de fora
# (HTTP 308 do Caddy). As duas tentativas inefetivas foram UFW `deny` (nao
# funciona: `ufw-user-input` tem `ACCEPT all` na regra 1, antes de qualquer
# deny) e DOCKER-USER (motivo acima). A terceira, em PREROUTING, funciona — e
# foi provada por tentativa externa, nao por leitura de regra.
set -u
log() { logger -t firewall-host -p daemon.notice "$*"; }

aplicar() {
  # 1. portas de container que nao devem ser alcancaveis de fora.
  #    Precisam de -i ens3: sem a interface a regra tambem alcanzaria trafego
  #    vindo das bridges do Docker e derrubaria rota interna.
  for p in 4300 4200 4100 3306 3000; do
    if ! iptables -C DOCKER-USER -i ens3 -p tcp --dport "$p" -j DROP 2>/dev/null; then
      iptables -I DOCKER-USER 1 -i ens3 -p tcp --dport "$p" -j DROP && log "DOCKER-USER: DROP $p"
    fi
  done

  # 2. ingress publico do plataforma-educacao (producao), fechado por decisao do
  #    solicitante em 2026-10-08. Vai em PREROUTING, antes do salto para DOCKER.
  if ! nft list chain ip nat PREROUTING 2>/dev/null | grep -q 'dport { 8080, 8084, 8443, 8444 }'; then
    nft insert rule ip nat PREROUTING iifname "ens3" tcp dport { 8080, 8084, 8443, 8444 } counter drop \
      && log "PREROUTING: DROP 8080,8084,8443,8444 (ingress plataforma-educacao)"
  fi
}
aplicar
