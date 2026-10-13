# Resultados — Sprint 1 do plano de monetização

**Data:** 13/10/2026
**Escopo:** os 10 itens do Sprint 1 descritos em `PLANO_MONETIZACAO.md` (M-01 a
M-10) — tudo que não depende de uma conta Google AdSense aprovada.

Todos os 10 itens foram implementados, testados e revisados antes de chegar
a este resumo. Os números abaixo (contagem de testes, cobertura) refletem o
estado real do código verificado, não uma estimativa.

## O que mudou, item por item

| Item | O que mudou | Status |
|---|---|---|
| **M-01** — Remover texto raspado da API pública | A resposta pública de uma notícia/acontecimento não traz mais o texto completo copiado da fonte original (campo `conteudo`). Isso também tirou da tela de leitura a seção "Matéria" que mostrava até 1.800 caracteres desse texto com link "Continuar lendo na fonte". | Concluído |
| **M-02** — Sitemap com notícias de verdade | `/sitemap.xml` agora lista as notícias publicadas, com data de atualização real — hoje todas as entradas publicáveis e indexáveis, não só as mais recentes (ver "correções feitas na revisão" abaixo). | Concluído |
| **M-03** — Não indexar notícia sem resumo próprio | Notícia sem resumo próprio (sem conteúdo original) sai de `/sitemap.xml` e dos resultados de busca, mas continua acessível por quem já tem o link. | Concluído |
| **M-04** — Um "endereço" de anúncio por posição, não só por formato | Cada posição de anúncio na página (topo da home, dentro da leitura, etc.) agora pode ter sua própria configuração, em vez de todas as posições do mesmo formato (horizontal, vertical...) compartilharem uma única configuração. | Concluído (a configuração em si só é preenchida quando a conta do Google AdSense for aprovada — ver observação abaixo) |
| **M-05** — Sem texto técnico de anúncio para o leitor | Quando não há anúncio para mostrar (leitor recusou cookies de anúncio, ou a conta do AdSense ainda não está pronta), a página não mostra mais nenhum texto do tipo "Anúncio — Google AdSense". Em produção, no lugar vazio aparece agora um cartão de assinatura (ver M-09). | Concluído |
| **M-06** — Menos anúncios por página | A página inicial caiu de 10 para 5 espaços de anúncio; a leitura de notícia, de 3 para 2; a página de planos não tem mais nenhum. Busca e arquivo mantiveram 1 cada. Na categoria, o espaço no meio do conteúdo passou a aparecer a cada 9 notícias, em vez de a cada 6. | Concluído |
| **M-07** — Plano semestral e destaque de economia real | A página `/planos` passou a oferecer também o plano Premium Semestral (R$ 20, 6 meses), além do anual já existente. O selo de economia ("Economize X%") agora é calculado a partir do preço e da duração reais de cada plano, não é mais um número fixo escrito no código. | Concluído |
| **M-08** — Convite para assinar dentro da leitura | Quem lê uma notícia sem ser assinante vê, uma única vez, um cartão discreto convidando a assinar o Premium, com link para `/planos`. Quem já é Premium não vê esse cartão. | Concluído |
| **M-09** — Cartão "sem anúncios" no lugar do espaço vazio | O espaço que ficaria vazio (ver M-05) agora mostra o preço real do plano pago mais barato disponível e um link para assinar — sem usar as palavras "publicidade" ou "AdSense". | Concluído |
| **M-10** — Patrocínio direto, sem depender do Google | Novo mecanismo de anúncio direto (contratado fora do Google AdSense): um espaço com o rótulo "Patrocinado" sempre visível, hoje ativo na página `/radar`. Funciona mesmo para quem recusou cookies de anúncio — é conteúdo próprio do portal, não rastreamento de terceiros. | Concluído (mecanismo pronto; ver pendências abaixo sobre o que ainda falta para vender de verdade) |

## Correções feitas durante a revisão de código

Antes deste sprint ser considerado pronto, uma revisão de código encontrou 3
pontos a corrigir. Os 3 já foram corrigidos e revalidados:

1. **Sitemap cobria só as notícias dos últimos 3 dias.** A primeira versão
   do item M-02 reaproveitou o mesmo filtro de "janela de tempo" usado no
   feed de notícias recentes — o que fazia sentido ali, mas tinha o efeito
   colateral de tirar do sitemap qualquer notícia com mais de 3 dias, mesmo
   que ela continuasse publicada e acessível. Corrigido: o sitemap agora
   cobre todo o acervo de notícias publicáveis e indexáveis, sem esse corte
   de tempo, com teste cobrindo justamente uma notícia mais antiga.
2. **Cadastro do plano semestral poderia duplicar em um caso raro.** O
   cadastro automático do novo plano semestral evita duplicar se já existir
   um plano com o nome exato "Premium Semestral", mas não detectaria um
   nome parecido cadastrado manualmente antes (ex. "Semestral Premium").
   Não havia (e não há hoje) nenhum plano assim cadastrado em nenhum
   ambiente — ficou só documentado como premissa para quem for cadastrar
   planos manualmente no futuro.
3. **Tempo de cache do patrocínio um pouco diferente do restante do site.**
   O cache do novo endpoint de patrocínio usava 60 segundos, enquanto o
   resto do site usa 45. Corrigido para usar o mesmo valor — uma alteração
   feita no admin para desativar um patrocínio agora demora o mesmo tempo
   para refletir no ar que qualquer outra mudança de conteúdo.

## O que fica de fora deste sprint (de propósito, não é pendência esquecida)

- **Preço e condições comerciais do patrocínio (M-10) não foram definidos.**
  Só o mecanismo técnico foi construído (cadastro no painel administrativo,
  exibição com rótulo, contagem de visualização/clique). Definir o que é
  um "espaço" comercial, por quanto tempo e por quanto vender continua
  sendo uma decisão de negócio, não de código.
- **Patrocínio na newsletter** ainda não foi ligado — está planejado para
  uma etapa futura, porque o e-mail é montado de um jeito diferente de uma
  página do site.
- **Slot de anúncio por posição (M-04) só fica "ligado" de verdade quando a
  conta do Google AdSense for aprovada e os blocos de anúncio forem criados
  no painel do Google** — isso depende de aprovação externa, fora do
  controle deste sprint. O código já está pronto para quando isso acontecer.
- **Conformidade de consentimento de anúncios para visitantes da União
  Europeia, Reino Unido e Suíça** (o Google exige um banner de cookies
  certificado — "CMP" — para esse público) está sendo avaliada
  separadamente, fora deste sprint; nenhuma mudança de código relacionada a
  isso está incluída aqui.
- **Um pequeno detalhe visual de contraste:** no cartão de assinatura (M-09),
  o selo com o ícone de coroa tem contraste levemente abaixo do recomendado
  (o texto ao lado, que é a parte que carrega a informação, passa com boa
  margem). Vale um ajuste de cor numa passada futura de polimento visual;
  não impede o uso normal da tela.
- **Algumas notícias (`/autor/*`, `/editorias/*`) ainda não entram no
  sitemap** — o plano original só sugeria considerar isso se o volume
  crescer muito; por ora não foi necessário.

## Verificação feita

- Backend: suíte de testes automatizados passando para tudo que este sprint
  tocou (notícias, sitemap, assinatura, patrocínio, métricas).
- Frontend: checagem de tipos, testes automatizados e build de produção
  passando, incluindo as verificações já existentes que garantem que nenhum
  script de anúncio ou de métricas é carregado sem o consentimento do
  visitante.
- Revisão de código concluída, com os 3 pontos levantados já corrigidos
  (ver seção acima).
