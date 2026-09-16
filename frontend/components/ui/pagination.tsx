"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { ChevronLeft, ChevronRight } from "lucide-react";

const Pagination = ({ className, ...props }: React.ComponentProps<"nav">) => (
  <nav className={cn("flex items-center justify-center", className)} aria-label="Pagination" {...props} />
);
Pagination.displayName = "Pagination";

const PaginationContent = React.forwardRef<HTMLUListElement, React.HTMLAttributes<HTMLUListElement>>(
  ({ className, ...props }, ref) => (
    <ul ref={ref} className={cn("flex items-center gap-1", className)} {...props} />
  )
);
PaginationContent.displayName = "PaginationContent";

const PaginationItem = React.forwardRef<HTMLLIElement, React.HTMLAttributes<HTMLLIElement>>(
  ({ className, ...props }, ref) => (
    <li ref={ref} className={cn("", className)} {...props} />
  )
);
PaginationItem.displayName = "PaginationItem";

const PaginationLink = ({
  className,
  isActive,
  size = "default",
  ...props
}: React.AnchorHTMLAttributes<HTMLAnchorElement> & { isActive?: boolean; size?: "default" | "sm" | "lg" }) => {
  const sizeClasses = {
    default: "h-9 w-9",
    sm: "h-8 w-8",
    lg: "h-10 w-10",
  };
  return (
    <a
      className={cn(
        "relative inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md text-sm font-medium transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        "motion-reduce:transition-none touch-manipulation",
        isActive
          ? "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]"
          : "text-[var(--cor-texto)] hover:bg-[var(--cor-borda)] hover:text-[var(--cor-primaria)]",
        sizeClasses[size],
        className
      )}
      aria-current={isActive ? "page" : undefined}
      {...props}
    />
  );
};
PaginationLink.displayName = "PaginationLink";

const PaginationPrevious = ({ className, size = "default", ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { size?: "default" | "sm" | "lg" }) => (
  <a
    className={cn(
      "inline-flex items-center justify-center gap-1 text-sm font-medium transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
      "disabled:pointer-events-none disabled:opacity-50",
      "motion-reduce:transition-none touch-manipulation min-h-[44px]",
      className
    )}
    {...props}
  >
    <ChevronLeft className="h-4 w-4" aria-hidden="true" />
    <span>Anterior</span>
  </a>
);
PaginationPrevious.displayName = "PaginationPrevious";

const PaginationNext = ({ className, size = "default", ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { size?: "default" | "sm" | "lg" }) => (
  <a
    className={cn(
      "inline-flex items-center justify-center gap-1 text-sm font-medium transition-colors",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
      "disabled:pointer-events-none disabled:opacity-50",
      "motion-reduce:transition-none touch-manipulation min-h-[44px]",
      className
    )}
    {...props}
  >
    <span>Próximo</span>
    <ChevronRight className="h-4 w-4" aria-hidden="true" />
  </a>
);
PaginationNext.displayName = "PaginationNext";

const PaginationEllipsis = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (
  <span className={cn("inline-flex h-9 w-9 items-center justify-center text-[var(--cor-texto-suave)]", className)} {...props}>
    <span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-texto-suave)]" />
    <span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-texto-suave)]" />
    <span className="h-1.5 w-1.5 rounded-full bg-[var(--cor-texto-suave)]" />
  </span>
);
PaginationEllipsis.displayName = "PaginationEllipsis";

export {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationPrevious,
  PaginationNext,
  PaginationEllipsis,
};