import clsx from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary: "btn-primary",
  secondary: "btn-glass",
  ghost:
    "inline-flex items-center justify-center gap-2 rounded-full px-3 py-1.5 text-xs font-normal text-muted transition-colors duration-150 hover:text-ink",
  danger:
    "inline-flex items-center justify-center gap-2 rounded-full border border-danger/30 px-3 py-1.5 text-xs font-medium text-danger transition-colors duration-150 hover:bg-danger/10",
};

const SIZES: Record<Size, string> = {
  sm: "h-7 px-3 text-2xs",
  md: "h-9 px-4",
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
        "select-none disabled:cursor-not-allowed disabled:opacity-40",
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
