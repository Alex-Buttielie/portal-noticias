"use client";

import * as React from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface CommandProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
}

const Command = React.forwardRef<HTMLDivElement, CommandProps>(
  ({ className, children, ...props }, ref) => (
    <div ref={ref} className={cn("flex h-full w-full flex-col overflow-hidden rounded-md bg-[var(--cor-fundo-elevado)] text-[var(--cor-texto)]", className)} {...props}>
      {children}
    </div>
  )
);
Command.displayName = "Command";

interface CommandInputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const CommandInput = React.forwardRef<HTMLInputElement, CommandInputProps>(
  ({ className, placeholder = "Buscar…", ...props }, ref) => (
    <div className="relative flex items-center border-b border-[var(--cor-borda)] p-2">
      <Search className="pointer-events-none absolute left-3 h-4 w-4 text-[var(--cor-texto-suave)]" aria-hidden="true" />
      <input
        ref={ref}
        type="search"
        inputMode="text"
        placeholder={placeholder}
        aria-label={props["aria-label"] ?? placeholder}
        className={cn(
          "flex h-10 w-full rounded-md bg-[var(--cor-fundo)] pl-10 pr-8 py-2 text-sm outline-none",
          "placeholder:text-[var(--cor-texto-suave)] placeholder:opacity-70",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-0 focus-visible:border-[var(--cor-primaria)]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "motion-reduce:transition-none touch-manipulation min-h-[44px]",
          className
        )}
        {...props}
      />
    </div>
  )
);
CommandInput.displayName = "CommandInput";

interface CommandListProps extends React.HTMLAttributes<HTMLDivElement> {}

const CommandList = React.forwardRef<HTMLDivElement, CommandListProps>(
  ({ className, children, ...props }, ref) => (
    <div ref={ref} className={cn("max-h-[300px] overflow-y-auto overflow-x-hidden p-2", className)} {...props}>
      {children}
    </div>
  )
);
CommandList.displayName = "CommandList";

interface CommandEmptyProps extends React.HTMLAttributes<HTMLDivElement> {}

const CommandEmpty = React.forwardRef<HTMLDivElement, CommandEmptyProps>(
  ({ className, children, ...props }, ref) => (
    <div ref={ref} className={cn("py-6 text-center text-sm text-[var(--cor-texto-suave)]", className)} {...props}>
      {children}
    </div>
  )
);
CommandEmpty.displayName = "CommandEmpty";

interface CommandGroupProps extends React.HTMLAttributes<HTMLDivElement> {}

const CommandGroup = React.forwardRef<HTMLDivElement, CommandGroupProps>(
  ({ className, children, ...props }, ref) => (
    <div ref={ref} className={cn("overflow-hidden", className)} {...props}>
      {children}
    </div>
  )
);
CommandGroup.displayName = "CommandGroup";

interface CommandSeparatorProps extends React.HTMLAttributes<HTMLDivElement> {}

const CommandSeparator = React.forwardRef<HTMLDivElement, CommandSeparatorProps>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("-mx-2 my-1 h-px bg-[var(--cor-borda)]", className)} {...props} />
  )
);
CommandSeparator.displayName = "CommandSeparator";

interface CommandItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  selected?: boolean;
}

const CommandItem = React.forwardRef<HTMLButtonElement, CommandItemProps>(
  ({ className, selected, children, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      role="option"
      aria-selected={selected}
      className={cn(
        "relative flex w-full cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors",
        "focus:bg-[var(--cor-primaria-suave)] focus:text-[var(--cor-primaria)]",
        "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        selected ? "bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]" : "",
        "motion-reduce:transition-none touch-manipulation min-h-[44px]",
        className
      )}
      {...props}
    >
      {children}
    </button>
  )
);
CommandItem.displayName = "CommandItem";

interface CommandShortcutProps extends React.HTMLAttributes<HTMLSpanElement> {}

const CommandShortcut = React.forwardRef<HTMLSpanElement, CommandShortcutProps>(
  ({ className, ...props }, ref) => (
    <span ref={ref} className={cn("ml-auto text-xs tracking-widest opacity-60", className)} {...props} />
  )
);
CommandShortcut.displayName = "CommandShortcut";

export {
  Command,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandShortcut,
  CommandSeparator,
};