"use client";

import * as React from "react";
import { GripVertical } from "lucide-react";
import { cn } from "@/lib/utils";

interface ResizablePanelGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  direction?: "horizontal" | "vertical";
}

const ResizablePanelGroup = React.forwardRef<HTMLDivElement, ResizablePanelGroupProps>(
  ({ className, direction = "horizontal", children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex h-full w-full",
        direction === "vertical" ? "flex-col" : "flex-row",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
);
ResizablePanelGroup.displayName = "ResizablePanelGroup";

interface ResizablePanelProps extends React.HTMLAttributes<HTMLDivElement> {
  defaultSize?: number;
  minSize?: number;
  maxSize?: number;
}

const ResizablePanel = React.forwardRef<HTMLDivElement, ResizablePanelProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("flex flex-1 overflow-auto", className)}
      {...props}
    >
      {children}
    </div>
  )
);
ResizablePanel.displayName = "ResizablePanel";

interface ResizableHandleProps extends React.HTMLAttributes<HTMLDivElement> {
  withHandle?: boolean;
}

const ResizableHandle = React.forwardRef<HTMLDivElement, ResizableHandleProps>(
  ({ className, withHandle = true, ...props }, ref) => (
    <div
      ref={ref}
      role="separator"
      aria-orientation="vertical"
      aria-label="Redimensionar painel"
      tabIndex={0}
      className={cn(
        "relative flex items-center justify-center bg-[var(--cor-borda)] transition-colors",
        "hover:bg-[var(--cor-primaria-suave)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)] focus-visible:ring-offset-2",
        "motion-reduce:transition-none touch-manipulation",
        withHandle ? "w-[10px]" : "w-px",
        className
      )}
      {...props}
    >
      {withHandle && (
        <div className="flex h-full w-full items-center justify-center">
          <GripVertical className="h-4 w-4 text-[var(--cor-texto-suave)]" aria-hidden="true" />
        </div>
      )}
    </div>
  )
);
ResizableHandle.displayName = "ResizableHandle";

export { ResizablePanelGroup, ResizablePanel, ResizableHandle };