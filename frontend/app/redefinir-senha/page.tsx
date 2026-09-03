import { Suspense } from "react";
import RedefinirSenhaConteudo from "./RedefinirSenhaConteudo";

export default function PaginaRedefinirSenha() {
  return (
    <Suspense fallback={<p className="texto-suave">Carregando...</p>}>
      <RedefinirSenhaConteudo />
    </Suspense>
  );
}
