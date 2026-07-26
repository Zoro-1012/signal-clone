"use client";

import { forwardRef, useId } from "react";

import { cn } from "@/lib/cn";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, className, id, ...rest },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const messageId = `${inputId}-message`;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-sm text-content-secondary">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={inputId}
        // Both are needed: aria-invalid marks the field, aria-describedby points
        // at the reason. Colour alone would exclude anyone not seeing it.
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? messageId : undefined}
        className={cn(
          "w-full rounded-lg bg-surface-hover px-4 py-2.5 text-content-primary",
          "placeholder:text-content-tertiary",
          "border border-transparent outline-none transition-colors",
          "focus:border-accent",
          error && "border-signal-red",
          className,
        )}
        {...rest}
      />
      {(error ?? hint) && (
        <p
          id={messageId}
          // Errors appear after a failed submit, so they must be announced;
          // static hints must not be, or every keystroke interrupts the reader.
          role={error ? "alert" : undefined}
          className={cn("mt-1.5 text-sm", error ? "text-signal-red" : "text-content-tertiary")}
        >
          {error ?? hint}
        </p>
      )}
    </div>
  );
});
