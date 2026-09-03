# Review Triggers

Regras que o `orchestrator` (dentro do `agentic-run`) e o `reviewer` consultam para decidir quando uma revisão de código (`code-review-contract.md`) é **obrigatória**, e em quais categorias focar. Fora destes gatilhos, a revisão é opcional/à critério do orchestrator — mas mudanças que alteram comportamento visível ao usuário sempre passam ao menos por `tester`.

## Gatilhos obrigatórios (genéricos)

- Qualquer mudança em **autenticação, autorização ou sessão** (login, permissões, controle de acesso).
- Qualquer mudança em **cobrança/pagamento/assinatura** (planos, preços, ciclo de cobrança, cancelamento).
- Qualquer mudança que **exponha ou altere dados pessoais** de usuários (cadastro, dados de contato, localização).
- Qualquer **migração de schema de banco de dados** ou mudança em modelo de dados existente (risco de perda/corrupção de dados).
- Qualquer mudança em **API pública** ou contrato usado por outros sistemas/consumidores.
- Qualquer mudança em **regras de moderação de conteúdo** ou nos critérios que decidem o que é publicado sem revisão prévia.
- Introdução de **nova dependência externa** (biblioteca de terceiros) — foco em licença, manutenção ativa e superfície de risco.
- Qualquer mudança tocando o **cálculo de reputação de autores credenciados** (afeta quem pode publicar sem moderação — seção 15 do BRD).
- Diffs acima de um tamanho considerável (referência: mais de ~300 linhas alteradas) — mesmo sem categoria sensível, o volume por si só justifica revisão.

## Gatilhos específicos deste projeto (portal de notícias)

Referência: `BRD_portal_noticias_versao_1.docx`.

- Mudanças no **credenciamento de jornalistas** (seção 13) — controla quem ganha poder de publicação editorial.
- Mudanças na **política de respeito e moderação** (seção 16) — risco de conteúdo abusivo passar sem bloqueio.
- Mudanças no **radar de tendências por localização** quando envolverem dados de geolocalização do usuário (seção 11).
- Mudanças no **produto B2B / arquitetura comercial** (seções 19-20) — afeta contratos com clientes corporativos.
- Mudanças em **direitos autorais e compliance** (seção 18) — risco jurídico direto.

## O que NÃO exige revisão obrigatória (mas pode passar por `agentic-verify`)

- Ajustes de copy/texto estático sem lógica associada.
- Mudanças puramente de estilo visual sem alteração de comportamento.
- Documentação isolada (sem código).

## Como usar

O `orchestrator` verifica esta lista ao montar o `implementation-contract.md`: se algum gatilho se aplica, marca a revisão como obrigatória no `task-plan.md` desde o início (não espera o `executor` terminar para descobrir). O `reviewer`, ao receber o escopo, também consulta esta lista para saber onde concentrar atenção, independente de quem pediu a revisão.
