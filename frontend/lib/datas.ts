/**
 * Formatadores editoriais determinísticos.
 *
 * O HTML pode ser gerado no servidor e hidratado em um navegador com outro
 * fuso. Por isso todo formato de data/hora do frontend passa por aqui, com a
 * mesma locale e o mesmo fuso usado pelo backend (config/settings.py).
 */

export const FUSO_EDITORIAL = "America/Sao_Paulo";
export const LOCALE_EDITORIAL = "pt-BR";

export type DataFormatavel = string | number | Date | null | undefined;

function paraData(valor: DataFormatavel): Date | null {
  if (valor === null || valor === undefined || valor === "") return null;
  const data = valor instanceof Date ? valor : new Date(valor);
  return Number.isNaN(data.getTime()) ? null : data;
}

function formatarData(
  valor: DataFormatavel,
  opcoes: Intl.DateTimeFormatOptions
): string {
  const data = paraData(valor);
  if (!data) return "";
  try {
    return new Intl.DateTimeFormat(LOCALE_EDITORIAL, {
      ...opcoes,
      timeZone: FUSO_EDITORIAL,
    }).format(data);
  } catch {
    return "";
  }
}

/** Data curta: DD/MM/AAAA. */
export function formatarDataCurta(valor: DataFormatavel): string {
  return formatarData(valor, { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Data sem ano, usada nos cards da Home: DD/MM. */
export function formatarDataSemAno(valor: DataFormatavel): string {
  return formatarData(valor, { day: "2-digit", month: "2-digit" });
}

/** Hora curta: HH:MM. */
export function formatarHora(valor: DataFormatavel): string {
  return formatarData(valor, { hour: "2-digit", minute: "2-digit" });
}

/** Hora com segundos, preservando o formato dos logs administrativos. */
export function formatarHoraComSegundos(valor: DataFormatavel): string {
  return formatarData(valor, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Linha compacta da Home: DD/MM • HH:MM. */
export function formatarDataHora(valor: DataFormatavel): string {
  const data = formatarDataSemAno(valor);
  const hora = formatarHora(valor);
  return data && hora ? `${data} • ${hora}` : "";
}

/** Formato completo de data/hora, equivalente ao formatador pt-BR anterior: DD/MM/AAAA, HH:MM:SS. */
export function formatarDataHoraCompleta(valor: DataFormatavel): string {
  return formatarData(valor, { dateStyle: "short", timeStyle: "medium" });
}

/** Data e hora curtas, sem segundos: DD/MM/AAAA, HH:MM. */
export function formatarDataHoraCompacta(valor: DataFormatavel): string {
  return formatarData(valor, { dateStyle: "short", timeStyle: "short" });
}

/** Data por extenso, como em 24 de setembro de 2026. */
export function formatarDataPorExtenso(valor: DataFormatavel): string {
  return formatarData(valor, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** Data por extenso com hora, como em 24 de setembro de 2026 às 20:17. */
export function formatarDataHoraPorExtenso(valor: DataFormatavel): string {
  return formatarData(valor, { dateStyle: "long", timeStyle: "short" });
}

/** Mês e ano para controles de calendário: setembro de 2026. */
export function formatarMesAno(valor: DataFormatavel): string {
  return formatarData(valor, { month: "long", year: "numeric" });
}

/** Ano editorial para créditos e rodapés: 2026. */
export function formatarAno(valor: DataFormatavel): string {
  return formatarData(valor, { year: "numeric" });
}

/**
 * Números em pt-BR. Não é um formato temporal, mas fica aqui para remover
 * os últimos usos diretos de formatação implícita e manter a locale explícita.
 */
export function formatarNumeroPtBR(valor: number): string {
  return new Intl.NumberFormat(LOCALE_EDITORIAL).format(valor);
}
