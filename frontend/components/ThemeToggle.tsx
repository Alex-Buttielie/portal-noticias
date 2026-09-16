"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon"
        disabled
        tabIndex={-1}
        aria-hidden="true"
        aria-label="Alternar tema"
        className={cn("h-9 w-9 shrink-0 rounded-full touch-manipulation min-h-[44px] min-w-[44px]")}
      >
        <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform motion-reduce:transition-none" aria-hidden="true" />
        <Moon className="absolute h-4 w-4 rotate-90 scale-50 transition-transform motion-reduce:transition-none" aria-hidden="true" />
      </Button>
    );
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn("h-9 w-9 shrink-0 rounded-full touch-manipulation min-h-[44px] min-w-[44px]")}
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      aria-label={`Alternar para tema ${theme === "dark" ? "claro" : "escuro"}`}
    >
      <Sun
        className="h-4 w-4 rotate-0 scale-100 transition-transform motion-reduce:transition-none dark:-rotate-90 dark:scale-0"
        aria-hidden="true"
      />
      <Moon
        className="absolute h-4 w-4 rotate-90 scale-50 transition-transform motion-reduce:transition-none dark:rotate-0 dark:scale-100"
        aria-hidden="true"
      />
      <span className="sr-only">{theme === "dark" ? "Tema claro" : "Tema escuro"}</span>
    </Button>
  );
}
