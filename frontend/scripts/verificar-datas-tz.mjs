import { readFile } from "node:fs/promises";
import ts from "typescript";

/*
 * Este check precisa rodar em Node 18/20, sem depender de tipos experimentais.
 * Em vez de duplicar a lógica de datas (o que deixaria o teste proteger outro
 * código), transpila o módulo TypeScript real com a dependência que já está
 * no devDependencies e o importa como módulo JavaScript puro.
 */
const fonte = await readFile(new URL("../lib/datas.ts", import.meta.url), "utf8");
const compilado = ts.transpileModule(fonte, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2020,
  },
  fileName: "datas.ts",
}).outputText;
const datas = await import(
  `data:text/javascript;charset=utf-8,${encodeURIComponent(compilado)}`
);

const dataCivil = "2026-09-23";
const instanteComFuso = "2026-09-23T21:30:00Z";

function conferir(condicao, mensagem) {
  if (!condicao) throw new Error(mensagem);
}

function conferirSaida(nome, valor, esperado) {
  conferir(
    valor === esperado,
    `${nome} incorreto: esperado ${JSON.stringify(esperado)}, recebido ${JSON.stringify(valor)}`
  );
}

// As expectativas são estáveis nos ICU embarcados no Node 18 e 20: locale e
// timezone são explícitos, e não usamos formatos deprecated nem celebratórios.
const resultado = {
  dataCivil: datas.formatarDataCurta(dataCivil),
  dataSemAno: datas.formatarDataSemAno(dataCivil),
  hora: datas.formatarHora(instanteComFuso),
  dataHora: datas.formatarDataHora(instanteComFuso),
  dataHoraCompleta: datas.formatarDataHoraCompleta(instanteComFuso),
  dataHoraCompacta: datas.formatarDataHoraCompacta(instanteComFuso),
  dataPorExtenso: datas.formatarDataPorExtenso(instanteComFuso),
  dataHoraPorExtenso: datas.formatarDataHoraPorExtenso(instanteComFuso),
  horaComSegundos: datas.formatarHoraComSegundos(instanteComFuso),
  mesAno: datas.formatarMesAno(instanteComFuso),
  ano: datas.formatarAno(instanteComFuso),
  numero: datas.formatarNumeroPtBR(1234567.89),
};
const resultadoEsperado = {
  dataCivil: "23/09/2026",
  dataSemAno: "23/09",
  hora: "18:30",
  dataHora: "23/09 • 18:30",
  dataHoraCompleta: "23/09/2026, 18:30:00",
  dataHoraCompacta: "23/09/2026, 18:30",
  dataPorExtenso: "quarta-feira, 23 de setembro de 2026",
  dataHoraPorExtenso: "23 de setembro de 2026 às 18:30",
  horaComSegundos: "18:30:00",
  mesAno: "setembro de 2026",
  ano: "2026",
  numero: "1.234.567,89",
};

for (const [nome, esperado] of Object.entries(resultadoEsperado)) {
  conferirSaida(nome, resultado[nome], esperado);
}

// Anos civis 0000–0099 precisam continuar distintos e com quatro dígitos em
// todos os formatadores que pedem year, inclusive dateStyle. 0095-02-29 é
// impossível no calendário gregoriano e não pode ser normalizada pelo Date.
function saidasQuePedemAno(valor) {
  return {
    dataCivil: datas.formatarDataCurta(valor),
    dataHoraCompleta: datas.formatarDataHoraCompleta(valor),
    dataHoraCompacta: datas.formatarDataHoraCompacta(valor),
    dataPorExtenso: datas.formatarDataPorExtenso(valor),
    dataHoraPorExtenso: datas.formatarDataHoraPorExtenso(valor),
    mesAno: datas.formatarMesAno(valor),
    ano: datas.formatarAno(valor),
  };
}

const saidasCivis = {
  "0000-01-01": saidasQuePedemAno("0000-01-01"),
  "0001-01-01": saidasQuePedemAno("0001-01-01"),
  "0096-02-29": saidasQuePedemAno("0096-02-29"),
  "0095-02-29": saidasQuePedemAno("0095-02-29"),
};
const saidasCivisEsperadas = {
  "0000-01-01": {
    dataCivil: "01/01/0000",
    dataHoraCompleta: "01/01/0000, 00:00:00",
    dataHoraCompacta: "01/01/0000, 00:00",
    dataPorExtenso: "sábado, 1 de janeiro de 0000",
    dataHoraPorExtenso: "1 de janeiro de 0000 às 00:00",
    mesAno: "janeiro de 0000",
    ano: "0000",
  },
  "0001-01-01": {
    dataCivil: "01/01/0001",
    dataHoraCompleta: "01/01/0001, 00:00:00",
    dataHoraCompacta: "01/01/0001, 00:00",
    dataPorExtenso: "segunda-feira, 1 de janeiro de 0001",
    dataHoraPorExtenso: "1 de janeiro de 0001 às 00:00",
    mesAno: "janeiro de 0001",
    ano: "0001",
  },
  "0096-02-29": {
    dataCivil: "29/02/0096",
    dataHoraCompleta: "29/02/0096, 00:00:00",
    dataHoraCompacta: "29/02/0096, 00:00",
    dataPorExtenso: "quarta-feira, 29 de fevereiro de 0096",
    dataHoraPorExtenso: "29 de fevereiro de 0096 às 00:00",
    mesAno: "fevereiro de 0096",
    ano: "0096",
  },
  "0095-02-29": {
    dataCivil: "",
    dataHoraCompleta: "",
    dataHoraCompacta: "",
    dataPorExtenso: "",
    dataHoraPorExtenso: "",
    mesAno: "",
    ano: "",
  },
};

for (const [data, esperadoPorFuncao] of Object.entries(saidasCivisEsperadas)) {
  for (const [nome, esperado] of Object.entries(esperadoPorFuncao)) {
    conferirSaida(`${data}/${nome}`, saidasCivis[data][nome], esperado);
  }
}
conferir(
  saidasCivis["0000-01-01"].dataCivil !== saidasCivis["0001-01-01"].dataCivil,
  "anos civis 0000 e 0001 colapsaram para a mesma saída"
);

console.log(JSON.stringify({ tz: process.env.TZ ?? "(não definido)", ...resultado }));
