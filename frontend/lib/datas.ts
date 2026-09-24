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

type DataCivil = {
  ano: number;
  mes: number;
  dia: number;
};

const DATA_CIVIL_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * Extrai uma data civil ISO sem timezone. O valor é uma informação de
 * calendário, não um instante UTC; por isso não pode passar por
 * `new Date("YYYY-MM-DD")`, que usa a especificação ECMAScript e interpreta
 * a string como UTC.
 */
function extrairDataCivil(valor: DataFormatavel): DataCivil | null {
  if (typeof valor !== "string") return null;
  const partes = DATA_CIVIL_RE.exec(valor.trim());
  if (!partes) return null;

  const ano = Number(partes[1]);
  const mes = Number(partes[2]);
  const dia = Number(partes[3]);
  // Valida o calendário sem depender da normalização de Date (por exemplo,
  // 31/02 poderia virar 02/03).
  const referencia = new Date(0);
  referencia.setUTCHours(0, 0, 0, 0);
  referencia.setUTCFullYear(ano, mes - 1, dia);
  if (
    referencia.getUTCFullYear() !== ano ||
    referencia.getUTCMonth() !== mes - 1 ||
    referencia.getUTCDate() !== dia
  ) {
    return null;
  }
  return { ano, mes, dia };
}

/**
 * Cria um instante neutro apenas para o Intl formatar os componentes de
 * uma data civil. A entrada continua sendo a data civil original; não há
 * conversão do input para UTC. O uso de UTC na referência evita que o fuso da
 * máquina (UTC, Tokyo etc.) desvie a data ao renderizá-la.
 */
function referenciaParaDataCivil(dataCivil: DataCivil): Date {
  const referencia = new Date(0);
  referencia.setUTCHours(0, 0, 0, 0);
  referencia.setUTCFullYear(dataCivil.ano, dataCivil.mes - 1, dataCivil.dia);
  return referencia;
}

function pareceDataCivil(valor: DataFormatavel): boolean {
  return typeof valor === "string" && DATA_CIVIL_RE.test(valor.trim());
}

function paraData(valor: DataFormatavel): Date | null {
  if (valor === null || valor === undefined || valor === "") return null;
  const dataCivil = extrairDataCivil(valor);
  if (dataCivil) return referenciaParaDataCivil(dataCivil);
  // Uma data ISO no formato de calendário, mas inválida, não deve virar uma
  // data normalizada pelo Date (por exemplo, 2026-02-30 -> 02/03).
  if (pareceDataCivil(valor)) return null;
  const data = valor instanceof Date ? valor : new Date(valor);
  return Number.isNaN(data.getTime()) ? null : data;
}

function formatarData(
  valor: DataFormatavel,
  opcoes: Intl.DateTimeFormatOptions
): string {
  const data = paraData(valor);
  if (!data) return "";
  const dataCivil = extrairDataCivil(valor);
  try {
    const formatador = new Intl.DateTimeFormat(LOCALE_EDITORIAL, {
      ...opcoes,
      // Para uma data civil, `data` já é uma referência de calendário em UTC;
      // para um instante normal, o fuso editorial continua obrigatório.
      timeZone: dataCivil ? "UTC" : FUSO_EDITORIAL,
    });

    if (dataCivil && dataCivil.ano <= 99) {
      // O ICU dos runtimes Node 18/20 apresenta 0000–0099 sem padding
      // ("1" para 0001, "96" para 0096). Reconstruímos somente a parte year
      // dos formatadores que a pedem; dia, mês, hora e o TZ UTC da referência
      // civil continuam exatamente os produzidos pelo Intl.
      const anoCivil = String(dataCivil.ano).padStart(4, "0");
      return formatador
        .formatToParts(data)
        .map((part) => (part.type === "year" ? anoCivil : part.value))
        .join("");
    }

    return formatador.format(data);
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
