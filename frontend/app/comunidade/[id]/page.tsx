import { DetalhePublicacao } from "./DetalhePublicacao";

// Server Component wrapper. No Next 15 `params` é um Promise e precisa ser
// awaited antes de virar prop. Existe porque o detalhe é um Client Component e o
// projeto está em React 18.3.1, que não expõe `use()` — resolver o id aqui
// (servidor) e passar `id: string` pronto mantém o comportamento idêntico ao do
// Next 14 sem exigir React 19.
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DetalhePublicacao id={id} />;
}
