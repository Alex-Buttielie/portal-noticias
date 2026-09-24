<!--
CONTRACT: implementation-contract
DONO: orchestrator (preenche) / executor, tester, reviewer (leem)
QUANDO É CRIADO: após o task-plan.md desta execução
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1400-tls-ingestao/
-->

# Implementation Contract — 20260924-1400-tls-ingestao

## Metadados
- **run_id:** 20260924-1400-tls-ingestao
- **Deriva de:** task-plan.md (20260924-1400-tls-ingestao)
- **Versão do contrato:** 1

## O que deve ser construído

### A. TLS no Nginx da topologia ativa
1. Parametrizar os três sites `infra/nginx/portal-{dev,homolog,prod}.conf`
   com um vhost HTTP e um vhost HTTPS por ambiente. O vhost HTTP deve redire-
   cionar tráfego normal em 301, mas servir
   `/.well-known/acme-challenge/`; o vhost HTTPS deve declarar
   `listen 443 ssl`, protocolo TLS 1.2/1.3 e certificados Certbot em
   `/etc/letsencrypt/live/<DOMAIN_FRONTEND>/`.
2. Usar marcadores de domínio explícitos, sem escolher um domínio real. O
   alias `www` é usado apenas em PROD quando o operador preencher o
   marcador; os demais ambientes podem renderizar o marcador de alias vazio.
3. Preservar `/healthz` no vhost HTTP apenas para loopback, encaminhando
   `X-Forwarded-Proto: https` ao Django para que o probe não entre em loop
   quando os flags estiverem ativos. O health check não deve ser aberto
   publicamente no canal HTTP.
4. Não duplicar HSTS no Nginx por padrão; o Django já o controla. A
   configuração deve passar `nginx -t` depois de renderizada com certificado
   de teste/real e os includes P1-4 existentes.

### B. Ativação segura do ambiente Django
1. Acrescentar a entrada booleana `tls_enabled` ao workflow reutilizável,
   com default seguro `false` para o bootstrap sem certificado.
2. Ao criar um `.env`, usar os três flags de cookie Secure e redirect como `true`
   somente quando `tls_enabled=true`; ao encontrar `.env` existente, não
   sobrescrevê-lo e falhar com mensagem explícita se os três flags não
   coincidirem com a entrada.
3. Fazer as origens públicas do build (`NEXT_PUBLIC_*`) acompanharem
   `http`/`https` conforme o estado do edge, evitando bundle HTTPS enquanto
   o vhost ainda é HTTP.
4. Fazer o probe de valificação usar o Gunicorn direto enquanto TLS está
   desligado e o vhost HTTPS real com `--resolve` quando `tls_enabled=true`,
   sem depender do nome DNS público nem confiar em um header enviado
   diretamente ao Gunicorn.
5. Expor `tls_enabled` explicitamente nos callers DEV/HOMOLOG/PROD,
   inicialmente `false` até o runbook ser executado.

### C. Runbook e decisões
1. Inserir em `infra/DEPLOY.md` a seção “Ativando TLS”, com Certbot
   escolhido em vez de Cloudflare Origin CA, valores a preencher, DNS,
   webroot, bootstrap HTTP-01, emissão, renderização, `nginx -t`, reload,
   testes, ordem de ativação do `.env`, flags, redeploy e renewal timer.
2. Descrever Cloudflare como camada opcional, dependente de conta do
   usuário, sem números de ganho não medidos e com cuidado para cache de
   respostas personalizadas.
3. Em `PROD_DECISOES.md`, registrar a recomendação de manter o
   `ingestao-service/` desligado, comparar Django e FastAPI/MongoDB,
   reconhecer o painel HTML próprio e registrar os riscos de manutenção,
   testes fora do CI, MongoDB exposto e defaults de custo desatualizados.
4. Em `ingestao-service/README.md`, adicionar apenas uma nota de status e a
   recomendação; não alterar código, compose ou testes.

## Áreas/arquivos esperados
- `infra/nginx/portal-dev.conf`
- `infra/nginx/portal-homolog.conf`
- `infra/nginx/portal-prod.conf`
- `.github/workflows/deploy.yml`
- `.github/workflows/deploy-dev.yml`
- `.github/workflows/deploy-homolog.yml`
- `.github/workflows/deploy-prod.yml`
- `.env.production.example`
- `infra/DEPLOY.md`
- `PROD_DECISOES.md`
- `ingestao-service/README.md`
- `agentic-framework/state/run-20260924-1400-tls-ingestao/implementation-history.md`
- Alterações fora dessa lista precisam ser justificadas no histórico.

## Interfaces afetadas
- Comportamento HTTP observável do Nginx: 80 deixa de servir a aplicação
  normalmente e passa a redirecionar para 443; 443 passa a exigir
  certificado válido. O challenge ACME e o probe loopback são exceções
  explícitas.
- Contrato de operação do deploy PM2: `tls_enabled` controla a criação ou
  validação de três flags de `.env`; `.env` existentes continuam
  preservados.
- Nenhuma API, schema de banco, código Django, TypeScript ou formato de
  payload é alterado.
- `DOMAIN_API` permanece uma entrada da variante Docker/Caddy; a topologia
  PM2 usa `DOMAIN_FRONTEND` como host único e `/api/` como caminho.

## Critérios de aceite (técnicos, testáveis)
1. Dado cada um dos três arquivos `portal-*.conf`, quando o texto é
   inspecionado, então existem um vhost 80, um vhost 443, `ssl_certificate`
   e `ssl_certificate_key` com marcadores parametrizados, e nenhuma string de
   domínio real foi introduzida.
2. Dado um vhost HTTP renderizado, quando uma requisição normal chega,
   então há `return 301 https://$host$request_uri`; quando a URI é
   `/.well-known/acme-challenge/`, então a location ACME é servida sem
   redirect; quando a URI é `/healthz` e a origem é externa, então o acesso
   é negado, e quando é loopback, então o probe é encaminhado.
3. Dado o workflow com `tls_enabled=false`, quando um `.env` novo é criado,
   então os três flags são `false` e as origens do frontend são `http`; dado
   `tls_enabled=true` e um `.env` novo, então os três flags são `true` e as
   origens são `https`.
4. Dado um `.env` existente, quando o valor de `tls_enabled` não coincide
   com qualquer um dos três flags, quando o deploy executa, então ele falha
   antes de iniciar PM2 e não sobrescreve o arquivo.
5. Dado o probe de validação, quando `DJANGO_SECURE_SSL_REDIRECT=true`,
   então a requisição local percorre o Nginx HTTPS com `--resolve` e pode
   retornar 200 sem seguir um redirect externo; antes da ativação, o probe
   direto ao Gunicorn continua funcionando.
6. Dado `.env.production.example`, quando um operador lê os defaults, então
   os três flags de Secure/redirect estão coerentes com a variante Caddy que
   termina TLS, e a documentação alerta que PM2 exige Certbot antes de true.
7. Dado o runbook, quando um humano segue a ordem documentada, então há
   comandos para instalar Certbot, criar webroot, obter certificado, renderizar
   domínio, validar/recarregar, testar, ativar flags, redeployar e verificar
   `certbot renew --dry-run`/timer.
8. Dado a documentação do `ingestao-service/`, quando um humano decide seu
   destino, então encontra uma recomendação explícita de manter desligado,
   uma comparação com o pipeline Django, o diferencial do painel `/painel` e
   os riscos do compose MongoDB e da suíte fora do CI.
9. Dado a validação local, quando Nginx é renderizado com certificados de
   teste e os includes P1-4, então `nginx -t` passa; quando o binário não
   existe, uma checagem de chaves balanceadas e diretivas obrigatórias é
   registrada; os quatro workflows passam parse YAML/actionlint.
10. Dado o escopo, quando `git status` é inspecionado, então nenhum arquivo
    de código Python/TypeScript de aplicação foi alterado por esta run e o
    diretório `ingestao-service/` não foi apagado.

## Não-objetivos
- Não ativar TLS, emitir certificado, alterar DNS, configurar conta
  Cloudflare ou recarregar a VPS.
- Não modificar o código de qualquer aplicação ou do microserviço.
- Não resolver a decisão humana de arquivar/ativar `ingestao-service/`.
- Não adicionar headers HSTS duplicados, dependências, funcionalidades de cache ou
 compressões não solicitadas.
- Não alterar o modelo de dados, endpoints, migrations ou contratos de API.

## Restrições técnicas
- **Performance:** somente configuração; não introduzir consultas/custo por
  request além do TLS esperado. O probe e ACME não podem ser capturados por
  cache/rate de escrita.
- **Segurança/privacidade:** TLS com CA verificável, cookies Secure somente
  depois de HTTPS real, health HTTP restrito a loopback, ACME sem redirecionar
  e nenhum segredo/domínio inventado no repositório.
- **Dependências permitidas:** nenhuma biblioteca nova; Certbot é uma
  dependência de sistema instalada pelo operador, não uma dependência de
  aplicação.
- **Estilo/convenções:** comentários em português, nomes de variáveis
  explícitos, preservar a topologia PM2 + Nginx e a variante P1-4.
- **Revisão:** mudança de superfície HTTP/TLS e volume de diff; reviewer
  deve conferir ordem de ativação, exceções ACME/health, marcador de
  domínio e não duplicação de headers.

## Definição de pronto (Definition of Done)
- [x] Critérios de aceite implementados no escopo de configuração/documentos
- [ ] Testes/validações finais registrados pelo tester
- [ ] Revisão de código aprovada, se exigida por `review-triggers.md`
- [x] Documentação atualizada
- [x] `implementation-history.md` completo e coerente
- [ ] `report.md` e entrada do historian (fases posteriores da pipeline)
