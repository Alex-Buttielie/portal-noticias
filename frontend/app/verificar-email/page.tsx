import { Suspense } from "react";
import VerificarEmailConteudo from "./VerificarEmailConteudo";

export default function PaginaVerificarEmail() {
  return (
    <Suspense fallback={<p className="texto-suave">Carregando...</p>}>
      <VerificarEmailConteudo />
    </Suspense>
  );
}
