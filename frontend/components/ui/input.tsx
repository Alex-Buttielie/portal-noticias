"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, placeholder, ...props }, ref) => {
    const resolvedPlaceholder =
      placeholder && !placeholder.endsWith("…") ? `${placeholder}…` : placeholder;
    return (
      <input
        type={type}
        placeholder={resolvedPlaceholder}
        className={cn(
          "flex h-10 w-full rounded-md border border-[var(--cor-borda)] bg-[var(--cor-fundo)] px-3 py-2 text-base sm:text-sm",
          "placeholder:text-[var(--cor-texto-suave)] placeholder:opacity-70",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-0 focus-visible:border-[var(--cor-primaria)]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "motion-reduce:transition-none touch-manipulation min-h-[44px]",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";

export { Input };
