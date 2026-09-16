/** Link de acessibilidade para quem navega por teclado/leitor de tela
 * pular a navegação repetida e ir direto ao conteúdo principal.
 * Tailwind: sr-only + focus:not-sr-only com ring visível e motion-reduce. */
export default function PularParaConteudo() {
  return (
    <a
      href="#conteudo-principal"
      className="pular-para-conteudo sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[1000] focus:inline-flex focus:min-h-[44px] focus:items-center focus:rounded-md focus:bg-[var(--cor-primaria)] focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-white focus:shadow-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cor-fundo)] motion-reduce:transition-none"
    >
      Pular para o conteúdo principal
    </a>
  );
}
