import * as React from "react";
import { cn } from "@/lib/utils";

interface ProseProps {
  children: React.ReactNode;
  className?: string;
  as?: "article" | "div" | "section";
}

export function Prose({ children, className, as: Component = "article" }: ProseProps) {
  return (
    <Component
      className={cn(
        "prose prose-[var(--cor-texto)] prose-headings:font-[var(--fonte-titulo)] prose-headings:text-[var(--cor-texto)] prose-headings:tracking-[-0.025em] prose-headings:text-wrap-balance",
        "prose-p:text-[var(--cor-texto)] prose-p:leading-relaxed prose-p:my-4",
        "prose-a:text-[var(--cor-primaria)] prose-a:no-underline prose-a:hover:underline",
        "prose-strong:text-[var(--cor-texto)]",
        "prose-em:text-[var(--cor-texto)]",
        "prose-blockquote:border-l-[var(--cor-primaria)] prose-blockquote:pl-4 prose-blockquote:italic prose-blockquote:text-[var(--cor-texto-suave)] prose-blockquote:my-4",
        "prose-ul:my-4 prose-ul:pl-6 prose-ul:list-disc prose-ul:text-[var(--cor-texto)]",
        "prose-ol:my-4 prose-ol:pl-6 prose-ol:list-decimal prose-ol:text-[var(--cor-texto)]",
        "prose-li:my-2 prose-li:leading-relaxed",
        "prose-h2:text-xl prose-h2:font-bold prose-h2:mt-8 prose-h2:mb-4",
        "prose-h3:text-lg prose-h3:font-semibold prose-h3:mt-6 prose-h3:mb-3",
        "prose-img:rounded-xl prose-img:my-6 prose-img:shadow-sm",
        "prose-figcaption:text-sm prose-figcaption:text-[var(--cor-texto-suave)] prose-figcaption:text-center prose-figcaption:mt-2",
        "prose-code:bg-[var(--cor-primaria-suave)] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[var(--cor-primaria)] prose-code:text-sm",
        "prose-pre:bg-[var(--cor-fundo-card)] prose-pre:border prose-pre:border-[var(--cor-borda)] prose-pre:rounded-xl prose-pre:p-4 prose-pre:overflow-x-auto prose-pre:my-6",
        "prose-pre_code:bg-transparent prose-pre_code:p-0 prose-pre_code:text-[var(--cor-texto)]",
        "max-w-none",
        className
      )}
    >
      {children}
    </Component>
  );
}

export function ProseHeading({
  level = 2,
  children,
  className,
}: {
  level?: 1 | 2 | 3 | 4;
  children: React.ReactNode;
  className?: string;
}) {
  const Tag = `h${level}` as keyof JSX.IntrinsicElements;
  return (
    <Tag
      className={cn(
        "font-[var(--fonte-titulo)] font-bold tracking-[-0.025em] text-wrap-balance text-[var(--cor-texto)]",
        level === 1 && "text-3xl lg:text-4xl",
        level === 2 && "text-2xl",
        level === 3 && "text-xl",
        level === 4 && "text-lg",
        className
      )}
    >
      {children}
    </Tag>
  );
}

export function ProseParagraph({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cn("text-[var(--cor-texto)] leading-relaxed my-4", className)}>
      {children}
    </p>
  );
}

export function ProseLead({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cn("text-lg text-[var(--cor-texto-suave)] leading-relaxed my-4 font-medium", className)}>
      {children}
    </p>
  );
}