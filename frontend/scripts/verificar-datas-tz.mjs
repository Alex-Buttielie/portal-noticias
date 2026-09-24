import {
  formatarDataCurta,
  formatarDataHora,
  formatarDataHoraCompleta,
  formatarDataHoraCompacta,
  formatarDataPorExtenso,
  formatarDataHoraPorExtenso,
  formatarHoraComSegundos,
  formatarMesAno,
  formatarAno,
  formatarNumeroPtBR,
} from "../lib/datas.ts";

const instante = "2026-09-24T00:30:05Z";

const resultado = {
  dataCurta: formatarDataCurta(instante),
  dataHora: formatarDataHora(instante),
  dataHoraCompleta: formatarDataHoraCompleta(instante),
  dataHoraCompacta: formatarDataHoraCompacta(instante),
  dataPorExtenso: formatarDataPorExtenso(instante),
  dataHoraPorExtenso: formatarDataHoraPorExtenso(instante),
  horaComSegundos: formatarHoraComSegundos(instante),
  mesAno: formatarMesAno(instante),
  ano: formatarAno(instante),
  numero: formatarNumeroPtBR(1234567.89),
};

console.log(JSON.stringify(resultado));
