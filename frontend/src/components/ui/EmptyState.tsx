import type { ReactNode } from "react";

type Props = {
  title: string;
  description?: string;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: Props) {
  return (
    <div className="rounded-md border border-dashed border-border bg-surface/40 px-6 py-10 text-center animate-fade-in">
      <p className="font-pixel text-lg text-text">{title}</p>
      {description ? (
        <p className="mx-auto mt-2 max-w-md text-sm text-muted leading-relaxed">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
    </div>
  );
}
