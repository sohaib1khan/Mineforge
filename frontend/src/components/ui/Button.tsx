import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variants: Record<Variant, string> = {
  primary: "bg-primary text-bg hover:opacity-90",
  secondary: "bg-surface border border-border text-text hover:bg-border/40",
  danger: "bg-danger text-white hover:opacity-90",
  ghost: "bg-transparent text-muted hover:text-text",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
};

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: Props) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-11 items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
