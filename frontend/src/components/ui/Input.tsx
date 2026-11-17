import type { InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export function Input({ label, error, id, className = "", ...props }: Props) {
  const inputId = id ?? props.name ?? label.toLowerCase().replace(/\s+/g, "-");
  return (
    <label className="block space-y-1.5" htmlFor={inputId}>
      <span className="text-sm text-muted">{label}</span>
      <input
        id={inputId}
        className={`min-h-11 w-full rounded-md border border-border bg-surface px-3 text-text placeholder:text-muted/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${className}`}
        {...props}
      />
      {error ? <span className="block text-sm text-danger">{error}</span> : null}
    </label>
  );
}
