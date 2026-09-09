import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

interface Base {
  rotulo: string;
  id: string;
  erro?: string;
  dica?: string;
  children?: ReactNode;
}

// Rótulo sempre ligado ao controle via `htmlFor` + `aria-describedby`
// apontando para dica/erro — leitor de tela anuncia contexto e validação.
function Envoltorio({ rotulo, id, erro, dica, children }: Base) {
  return (
    <div className="campo">
      <label className="campo__rotulo" htmlFor={id}>
        {rotulo}
      </label>
      {children}
      {dica && (
        <p className="campo__dica" id={`${id}-dica`}>
          {dica}
        </p>
      )}
      {erro && (
        <p className="campo__erro" id={`${id}-erro`} role="alert">
          {erro}
        </p>
      )}
    </div>
  );
}

function descritosPara(id: string, dica?: string, erro?: string): string | undefined {
  return [dica ? `${id}-dica` : "", erro ? `${id}-erro` : ""].filter(Boolean).join(" ") || undefined;
}

interface CampoTexto extends Base, Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {}

export function CampoTexto({ rotulo, id, erro, dica, ...resto }: CampoTexto) {
  return (
    <Envoltorio rotulo={rotulo} id={id} erro={erro} dica={dica}>
      <input
        id={id}
        className={`campo__controle${erro ? " campo__controle--invalido" : ""}`}
        aria-invalid={Boolean(erro)}
        aria-describedby={descritosPara(id, dica, erro)}
        {...resto}
      />
    </Envoltorio>
  );
}

interface CampoArea extends Base, Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {}

export function CampoAreaTexto({ rotulo, id, erro, dica, ...resto }: CampoArea) {
  return (
    <Envoltorio rotulo={rotulo} id={id} erro={erro} dica={dica}>
      <textarea
        id={id}
        className={`campo__controle${erro ? " campo__controle--invalido" : ""}`}
        aria-invalid={Boolean(erro)}
        aria-describedby={descritosPara(id, dica, erro)}
        {...resto}
      />
    </Envoltorio>
  );
}

interface CampoEscolha extends Base, Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {}

export function CampoSelecao({ rotulo, id, erro, dica, children, ...resto }: CampoEscolha) {
  return (
    <Envoltorio rotulo={rotulo} id={id} erro={erro} dica={dica}>
      <select
        id={id}
        className={`campo__controle${erro ? " campo__controle--invalido" : ""}`}
        aria-invalid={Boolean(erro)}
        aria-describedby={descritosPara(id, dica, erro)}
        {...resto}
      >
        {children}
      </select>
    </Envoltorio>
  );
}
