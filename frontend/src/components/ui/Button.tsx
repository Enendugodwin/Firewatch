import clsx from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-fire-medium text-[#1a1006] hover:bg-fire-low border border-fire-medium/60 font-semibold",
  secondary: "bg-raised text-ink border border-line hover:border-faint/70 hover:bg-raised/80",
  ghost: "text-muted hover:text-ink hover:bg-raised/70 border border-transparent",
  danger: "bg-danger/10 text-danger border border-danger/40 hover:bg-danger/20",
};

const SIZES: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3.5 text-sm gap-2",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={clsx(
        "inline-flex select-none items-center justify-center rounded-md transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-45",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
