import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

// shadcn Label
const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("text-sm font-semibold leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70", className)}
    {...props}
  />
));
Label.displayName = LabelPrimitive.Root.displayName;

// shadcn Input — text-[16px] em mobile evita zoom iOS (M3), sm:text-sm mantém densidade desktop
const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 min-h-[44px] w-full touch-manipulation rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-[16px] ring-offset-[var(--cor-fundo)] sm:text-sm",
        "placeholder:text-[var(--cor-texto-suave)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "motion-reduce:transition-none transition-colors",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Input.displayName = "Input";

// shadcn Textarea
const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full touch-manipulation rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-[16px] ring-offset-[var(--cor-fundo)] sm:text-sm",
        "placeholder:text-[var(--cor-texto-suave)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "motion-reduce:transition-none transition-colors",
        className
      )}
      ref={ref}
      {...props}
    />
  );
});
Textarea.displayName = "Textarea";

// shadcn Select (native select styled, with radix-like focus)
const Select = React.forwardRef<HTMLSelectElement, React.ComponentProps<"select">>(({ className, children, ...props }, ref) => {
  return (
    <select
      className={cn(
        "flex h-10 min-h-[44px] w-full touch-manipulation rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo-elevado)] px-3 py-2 text-[16px] ring-offset-[var(--cor-fundo)] sm:text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "motion-reduce:transition-none transition-colors",
        className
      )}
      ref={ref}
      {...props}
    >
      {children}
    </select>
  );
});
Select.displayName = "Select";

interface Base {
  rotulo: string;
  id: string;
  erro?: string;
  dica?: string;
  children?: React.ReactNode;
}

function Envoltorio({ rotulo, id, erro, dica, children }: Base) {
  const idErro = erro ? `${id}-erro` : undefined;
  const idDica = dica ? `${id}-dica` : undefined;
  return (
    <div className={cn("grid gap-1.5")}>
      <Label htmlFor={id}>{rotulo}</Label>
      {children}
      {dica && (
        <p id={idDica} className="text-xs text-[var(--cor-texto-suave)]">
          {dica}
        </p>
      )}
      {erro && (
        <p id={idErro} role="alert" className="text-xs font-medium text-[var(--cor-erro)]">
          {erro}
        </p>
      )}
    </div>
  );
}

interface CampoTexto extends Base, Omit<React.InputHTMLAttributes<HTMLInputElement>, "id"> {}

export function CampoTexto({ rotulo, id, erro, dica, placeholder, ...resto }: CampoTexto) {
  const descritoPor = [dica ? `${id}-dica` : "", erro ? `${id}-erro` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <Envoltorio rotulo={rotulo} id={id} erro={erro} dica={dica}>
      <Input
        id={id}
        name={resto.name ?? id}
        aria-invalid={Boolean(erro)}
        aria-describedby={descritoPor}
        placeholder={placeholder ?? "Digite…"}
        autoComplete={resto.autoComplete ?? "off"}
        className={cn(erro && "border-[var(--cor-erro)] focus-visible:ring-[var(--cor-erro)]")}
        {...resto}
      />
    </Envoltorio>
  );
}

interface CampoArea extends Base, Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {}

export function CampoAreaTexto({ rotulo, id, erro, dica, placeholder, ...resto }: CampoArea) {
  const descritoPor = [dica ? `${id}-dica` : "", erro ? `${id}-erro` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <Envoltorio rotulo={rotulo} id={id} erro={erro} dica={dica}>
      <Textarea
        id={id}
        name={resto.name ?? id}
        aria-invalid={Boolean(erro)}
        aria-describedby={descritoPor}
        placeholder={placeholder ?? "Digite…"}
        autoComplete={resto.autoComplete ?? "off"}
        className={cn(erro && "border-[var(--cor-erro)] focus-visible:ring-[var(--cor-erro)]")}
        {...resto}
      />
    </Envoltorio>
  );
}

interface CampoEscolha extends Base, Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "id"> {}

export function CampoSelecao({ rotulo, id, erro, dica, children, ...resto }: CampoEscolha) {
  const descritoPor = [dica ? `${id}-dica` : "", erro ? `${id}-erro` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <Envoltorio rotulo={rotulo} id={id} erro={erro} dica={dica}>
      <Select
        id={id}
        name={resto.name ?? id}
        aria-invalid={Boolean(erro)}
        aria-describedby={descritoPor}
        className={cn(erro && "border-[var(--cor-erro)] focus-visible:ring-[var(--cor-erro)]")}
        {...resto}
      >
        {children}
      </Select>
    </Envoltorio>
  );
}

export { Label, Input, Textarea, Select };
