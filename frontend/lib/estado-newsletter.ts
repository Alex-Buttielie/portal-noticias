/**
 * A regra visual do estado de uma inscrição de newsletter (double opt-in).
 *
 * POR QUE ESTE ARQUIVO EXISTE, E POR QUE NÃO É UM `if` NO JSX
 * =============================================================
 * A inscrição tem TRÊS estados (`pendente`, `confirmada`, `rejeitada` — ver
 * `EstadoInscricaoNewsletter` em `lib/api.ts`), e a cor da região de status
 * depende de qual deles é. Dois formulários mostram esse estado:
 *
 *   - `app/newsletter/NewsletterForm.tsx` (a página inteira);
 *   - `components/NewsletterMiniForm.tsx` (a caixa da Home).
 *
 * Se cada um tivesse o seu ternário, os dois divergiriam no primeiro ajuste de
 * cor — e a divergência seria do tipo que ninguém nota: a Home diria que
 * "pendente" é sucesso e a página da newsletter diria que é aviso, sem que
 * nenhuma das duas estivesse errada por si.
 *
 * Está em `lib/` e não em `app/newsletter/` porque `components/` não deveria
 * importar de `app/`: a direção de dependência do projeto é `app → components
 * → lib`, e invertê-la por causa de uma função de dez linhas seria o tipo de
 * atalho que a próxima pessoa não consegue explicar.
 *
 * POR QUE `pendente` É VERDE E NÃO ÂMBAR
 * =======================================
 * A pessoa fez tudo que podia: pediu, e o portal registrou. O que falta é um
 * clique que depende DELA, e um âmbar faria ela concluir que deu algo errado e
 * repetir o pedido — que é a pior resposta possível quando ela já está
 * esperando um e-mail. `rejeitada` também sai com a cor neutra: chegar até ela
 * pela UI exige recarregar a página depois de cancelar, e a mensagem de erro
 * do cancelamento já é a informação útil.
 *
 * A `confirmada` é a única que usa o verde de sucesso cheio, e é a única em que
 * "Inscrição confirmada. Bom leitura!" é verdade.
 */

import type { EstadoInscricaoNewsletter } from "./api";

/**
 * Classe CSS da região de status de uma inscrição.
 *
 * Aceita `null` (nenhum estado ainda) e cai em `pendente` — que é o caso mais
 * conservador: antes de qualquer resposta do servidor, não se pode afirmar
 * que a inscrição está confirmada.
 */
export function classeDoEstadoNewsletter(estado: EstadoInscricaoNewsletter | null): string {
  if (estado === "confirmada") {
    return "border-[var(--cor-sucesso)] bg-[var(--cor-sucesso-suave)] text-[var(--cor-sucesso)]";
  }
  return "border-[var(--cor-primaria)] bg-[var(--cor-primaria-suave)] text-[var(--cor-texto)]";
}