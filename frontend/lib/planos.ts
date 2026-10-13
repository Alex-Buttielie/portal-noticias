import type { Plano } from "./api";

/**
 * M-07 (run 20261012-1806-monetizacao-sprint1) — destaque de economia em
 * `/planos`, calculado a partir do PREÇO e da DURAÇÃO reais de cada plano
 * pago ativo (nunca um número fixo no código — ver BRD §6, "preço e
 * duração totalmente editáveis pelo admin").
 */
export interface PlanoComDestaque extends Plano {
  /** `preco ÷ duracao_dias`. `null` quando a duração não permite o cálculo
   *  (0 dias, ou `preco` não numérico). */
  custoPorDia: number | null;
  /** Quanto este plano é mais barato por dia que o pior custo/dia entre os
   *  planos pagos ativos, em %. `null` sem pelo menos 2 planos pagos
   *  comparáveis (nada para comparar — nunca inventa um número). */
  economiaPercent: number | null;
  /** `true` só no plano com o MENOR custo por dia (melhor negócio) — é o
   *  que ganha o destaque visual na página. Com só 1 plano pago, nenhum
   *  ganha destaque por economia (ver `app/planos/page.tsx`, que trata o
   *  caso de 1 plano separadamente com o rótulo genérico "Mais popular"). */
  destaque: boolean;
}

/**
 * Recebe só os planos PAGOS ativos (sem o `free`) e devolve cada um com o
 * custo por dia e, quando há pelo menos 2 planos comparáveis, a economia
 * percentual do mais barato por dia em relação ao mais caro por dia.
 */
export function calcularDestaquePlanos(planosPagos: Plano[]): PlanoComDestaque[] {
  const comCusto = planosPagos.map((p) => {
    const preco = Number(p.preco);
    const custoPorDia = p.duracao_dias > 0 && Number.isFinite(preco) ? preco / p.duracao_dias : null;
    return { ...p, custoPorDia, economiaPercent: null as number | null, destaque: false };
  });

  const custos = comCusto.map((p) => p.custoPorDia).filter((c): c is number => c !== null);
  if (custos.length < 2) return comCusto;

  const piorCustoPorDia = Math.max(...custos);
  const melhorCustoPorDia = Math.min(...custos);

  return comCusto.map((p) => {
    if (p.custoPorDia === null) return p;
    const economiaPercent =
      piorCustoPorDia > 0 && p.custoPorDia < piorCustoPorDia
        ? Math.round((1 - p.custoPorDia / piorCustoPorDia) * 100)
        : null;
    return { ...p, economiaPercent, destaque: p.custoPorDia === melhorCustoPorDia };
  });
}
