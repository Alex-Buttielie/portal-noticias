"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Calendar } from "./calendar";
import { Popover, PopoverContent, PopoverTrigger } from "./popover";
import { Button } from "./button";
import { CalendarIcon } from "lucide-react";

interface DatePickerProps {
  className?: string;
  value?: Date;
  onChange?: (date: Date | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
}

const DatePicker = React.forwardRef<HTMLButtonElement, DatePickerProps>(
  ({ className, value, onChange, placeholder = "Selecionar data…", disabled }, ref) => {
    return (
      <Popover>
        <PopoverTrigger asChild>
          <Button
            ref={ref}
            variant="outline"
            className={cn("w-full justify-between text-left font-normal", className)}
            disabled={disabled}
          >
            <CalendarIcon className="mr-2 h-4 w-4 opacity-50" aria-hidden="true" />
            {value ? value.toLocaleDateString("pt-BR") : <span className="text-[var(--cor-texto-suave)]">{placeholder}</span>}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={value}
            onSelect={onChange}
            initialFocus
            disabled={disabled}
          />
        </PopoverContent>
      </Popover>
    );
  }
);
DatePicker.displayName = "DatePicker";

export { DatePicker };