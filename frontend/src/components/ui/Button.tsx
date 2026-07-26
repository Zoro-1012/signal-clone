"use client";

import { forwardRef } from "react";

import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-content-on-accent hover:bg-accent-hover",
  secondary: "bg-surface-hover text-content-primary hover:bg-surface-active",
  ghost: "text-content-primary hover:bg-surface-hover",
  danger: "bg-signal-red text-white hover:opacity-90",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, fullWidth, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      // A loading button must not be clickable again, or an unlucky double-click
      // sends the request twice.
      disabled={disabled ?? loading}
      // Tells assistive technology the control is busy rather than merely broken.
      aria-busy={loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-medium",
        "transition-colors duration-150",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        SIZES[size],
        fullWidth && "w-full",
        className,
      )}
      {...rest}
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
});
