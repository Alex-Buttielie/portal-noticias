# Task Plan — 20260902-1600-frontend-radar-newsletter-landing

Solicitado por: usuário ("aplique DDD... e siga na implementação do meu MVP" → escolha explícita via AskUserQuestion: "Continuar implementando mais funcionalidades"). Formato conciso.

## Objetivo
Fechar a lacuna de frontend para os três módulos "consumer-facing" que ainda não tinham UI: Radar de Tendências, Newsletter e Landing/Lista de Espera. B2B e Métricas (mais admin/internos) ficam para uma próxima leva.

## Escopo desta execução
1. `frontend/app/radar/page.tsx` — tendências por país/estado/cidade, aviso de metodologia, evolução gated a Premium, salvar localidade.
2. Seção de Newsletter embutida em `frontend/app/minha-conta/page.tsx` (não é página própria — é gerenciamento de conta, mesmo padrão de "Assinatura"/"Histórico de pagamentos" já existentes na mesma página).
3. `frontend/app/lista-de-espera/page.tsx` — página pública (sem login), com breve proposta de valor + formulário, fechando o Critério de aceite 5 deixado pendente em `run-20260902-1517-landing-lista-espera`.
4. `frontend/components/Header.tsx` — link de navegação para `/radar`.
5. `frontend/lib/api.ts` — funções cliente para os três módulos (feito na iteração anterior, antes desta execução formalizar o run).

## Critérios de aceite
1. Visitante (sem login) vê tendências do radar e pode filtrar por país/estado/cidade.
2. Usuário Premium vê a evolução de um assunto; usuário Free vê aviso de que é recurso Premium (sem chamar o endpoint gated).
3. Usuário autenticado salva uma localidade de interesse.
4. Usuário autenticado se inscreve/cancela a newsletter a partir de "Minha conta", escolhendo tipo (padrão/categoria/personalizada — personalizada só visível a Premium).
5. Visitante (sem login) se cadastra na lista de espera preenchendo nome, e-mail, interesses, localidade, canal preferido e aceite de comunicação.

## Nota sobre DDD
Nenhuma mudança de backend nesta execução — os três módulos já expõem os endpoints necessários via seus respectivos `services.py`. O frontend consome exclusivamente via `lib/api.ts`, sem lógica de negócio duplicada no cliente (ex.: o gate de "personalizada" é aplicado no backend via `RecursoGatedError`; o frontend só evita a chamada óbvia mostrando a opção apenas a Premium, mas não depende disso como única defesa).

## Risco conhecido (mesma limitação de toda a sessão)
Ferramentas de execução (Bash rodando node/python, Agent, Browser) seguem indisponíveis por falha do classificador de segurança. Nada deste código foi rodado, buildado ou testado de fato. Revisão manual cuidadosa foi o único mecanismo de validação disponível.
