import { redirect } from "next/navigation";

// Página antiga, mantida só como redirect: o conteúdo real e atualizado
// (retenção, operador de diagnóstico, ausência de gravação de tela) vive em
// /privacidade. Duplicar o texto aqui divergiria a cada atualização de LGPD.
export default function Page() {
  redirect("/privacidade");
}
