import type { SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
};

export function Select({ label, id, className = "", children, ...props }: Props) {
  const selectId = id ?? props.name ?? label.toLowerCase().replace(/\s+/g, "-");
  return (
    <label className="block space-y-1.5" htmlFor={selectId}>
      <span className="text-sm text-muted">{label}</span>
      <select
        id={selectId}
        className={`min-h-11 w-full rounded-md border border-border bg-surface px-3 text-text focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${className}`}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}
