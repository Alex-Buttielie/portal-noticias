"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

function getDaysInMonth(date: Date): Date[] {
  const year = date.getFullYear();
  const month = date.getMonth();
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const daysInMonth = lastDay.getDate();
  const startingDay = firstDay.getDay();

  const days: Date[] = [];
  for (let i = 0; i < startingDay; i++) {
    const prevMonthDay = new Date(year, month, i - startingDay + 1);
    days.push(prevMonthDay);
  }
  for (let i = 1; i <= daysInMonth; i++) {
    days.push(new Date(year, month, i));
  }
  const remainingDays = 42 - days.length;
  for (let i = 1; i <= remainingDays; i++) {
    const nextMonthDay = new Date(year, month + 1, i);
    days.push(nextMonthDay);
  }
  return days;
}

function formatMonthYear(date: Date): string {
  return date.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
}

interface CalendarProps {
  className?: string;
  selected?: Date;
  onSelect?: (date: Date) => void;
  initialFocus?: boolean;
  disabled?: boolean;
  mode?: "single";
}

const Calendar = React.forwardRef<HTMLDivElement, CalendarProps>(
  ({ className, selected, onSelect, disabled = false, mode, initialFocus, ...props }, ref) => {
    void mode;
    void initialFocus;
    const [currentMonth, setCurrentMonth] = React.useState(selected || new Date());

    const days = getDaysInMonth(currentMonth);
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const handleDayClick = (day: Date) => {
      if (disabled) return;
      onSelect?.(day);
    };

    const isSelected = (day: Date) =>
      selected &&
      day.getDate() === selected.getDate() &&
      day.getMonth() === selected.getMonth() &&
      day.getFullYear() === selected.getFullYear();

    const isToday = (day: Date) =>
      day.getDate() === today.getDate() &&
      day.getMonth() === today.getMonth() &&
      day.getFullYear() === today.getFullYear();

    const isOutsideMonth = (day: Date) =>
      day.getMonth() !== currentMonth.getMonth();

    return (
      <div ref={ref} className={cn("w-full", className)} {...props}>
        <div className="flex items-center justify-between mb-4">
          <button
            type="button"
            onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}
            disabled={disabled}
            className={cn(
              "inline-flex h-9 w-9 items-center justify-center rounded-full text-sm font-medium transition-colors",
              "hover:bg-[var(--cor-borda)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
              "disabled:pointer-events-none disabled:opacity-50",
              "motion-reduce:transition-none touch-manipulation min-h-[44px] min-w-[44px]"
            )}
            aria-label="Mês anterior"
          >
            <ChevronLeft className="h-5 w-5" aria-hidden="true" />
          </button>
          <div className="text-center">
            <span className="text-sm font-medium text-[var(--cor-texto)]">
              {formatMonthYear(currentMonth)}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}
            disabled={disabled}
            className={cn(
              "inline-flex h-9 w-9 items-center justify-center rounded-full text-sm font-medium transition-colors",
              "hover:bg-[var(--cor-borda)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
              "disabled:pointer-events-none disabled:opacity-50",
              "motion-reduce:transition-none touch-manipulation min-h-[44px] min-w-[44px]"
            )}
            aria-label="Próximo mês"
          >
            <ChevronRight className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="grid grid-cols-7 gap-0 text-center">
          {["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"].map((day) => (
            <div key={day} className="h-8 text-[var(--cor-texto-suave)] text-xs font-medium">
              {day}
            </div>
          ))}
          {days.map((day, index) => (
            <button
              key={index}
              type="button"
              onClick={() => handleDayClick(day)}
              disabled={disabled}
              className={cn(
                "relative p-1 text-center",
                isSelected(day) && "bg-[var(--cor-primaria)] text-[var(--cor-texto-invertido)]",
                isToday(day) && !isSelected(day) && "bg-[var(--cor-primaria-suave)] text-[var(--cor-primaria)]",
                isOutsideMonth(day) && "text-[var(--cor-texto-suave)] opacity-50",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--cor-foco)]",
                "disabled:pointer-events-none disabled:opacity-50",
                "motion-reduce:transition-none touch-manipulation min-h-[44px] min-w-[44px]",
                "rounded-full"
              )}
              aria-selected={isSelected(day)}
              aria-current={isToday(day) ? "date" : undefined}
              aria-disabled={disabled || isOutsideMonth(day)}
            >
              <span className="relative flex h-9 w-9 items-center justify-center rounded-full text-sm font-medium">
                {day.getDate()}
              </span>
            </button>
          ))}
        </div>
      </div>
    );
  }
);
Calendar.displayName = "Calendar";

export { Calendar };