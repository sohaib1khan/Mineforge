import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Markdown from "react-markdown";

import { EmptyState } from "../../components/ui/EmptyState";
import { SkeletonLines } from "../../components/ui/Skeleton";
import { fetchHelpGuide, fetchHelpGuides } from "../../lib/api";

export function HelpPage() {
  const listQuery = useQuery({
    queryKey: ["help-guides"],
    queryFn: fetchHelpGuides,
  });
  const guides = useMemo(
    () => [...(listQuery.data?.guides ?? [])].sort((a, b) => a.order - b.order),
    [listQuery.data],
  );
  const [slug, setSlug] = useState<string | null>(null);
  const activeSlug = slug ?? guides[0]?.slug ?? null;

  const guideQuery = useQuery({
    queryKey: ["help-guide", activeSlug],
    queryFn: () => fetchHelpGuide(activeSlug!),
    enabled: activeSlug != null,
  });

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="font-pixel text-2xl text-text">Help</h1>
        <p className="max-w-xl text-muted leading-relaxed">
          Built-in hosting guides for connecting, ports, DNS, versions, and add-ons.
        </p>
      </div>

      {listQuery.isLoading ? <SkeletonLines count={4} /> : null}
      {listQuery.isError ? (
        <p className="text-sm text-danger" role="alert">
          Could not load guides.
        </p>
      ) : null}

      {!listQuery.isLoading && guides.length === 0 ? (
        <EmptyState
          title="No guides available"
          description="Help content is missing from this install."
        />
      ) : null}

      {guides.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <nav aria-label="Help topics" className="space-y-1">
            {guides.map((g) => (
              <button
                key={g.slug}
                type="button"
                className={`min-h-11 w-full rounded-md px-3 text-left text-sm transition-colors ${
                  activeSlug === g.slug
                    ? "bg-primary/15 text-primary"
                    : "text-muted hover:bg-border/40 hover:text-text"
                }`}
                onClick={() => setSlug(g.slug)}
              >
                {g.title}
              </button>
            ))}
          </nav>

          <article className="rounded-md border border-border bg-surface/70 p-5 page-enter">
            {guideQuery.isLoading ? <SkeletonLines count={5} /> : null}
            {guideQuery.data ? (
              <div className="help-prose space-y-3 text-sm leading-relaxed text-text">
                <p className="text-muted">{guideQuery.data.summary}</p>
                <Markdown
                  components={{
                    h1: ({ children }) => (
                      <h2 className="font-pixel text-xl text-text">{children}</h2>
                    ),
                    h2: ({ children }) => (
                      <h3 className="font-pixel text-lg text-text">{children}</h3>
                    ),
                    ul: ({ children }) => (
                      <ul className="list-disc space-y-1 pl-5">{children}</ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="list-decimal space-y-1 pl-5">{children}</ol>
                    ),
                    code: ({ children }) => (
                      <code className="rounded bg-border/40 px-1 py-0.5 text-xs">
                        {children}
                      </code>
                    ),
                    p: ({ children }) => <p>{children}</p>,
                    strong: ({ children }) => (
                      <strong className="font-semibold text-text">{children}</strong>
                    ),
                    a: ({ href, children }) => (
                      <a
                        className="text-accent underline-offset-2 hover:underline"
                        href={href}
                      >
                        {children}
                      </a>
                    ),
                  }}
                >
                  {guideQuery.data.markdown}
                </Markdown>
              </div>
            ) : null}
          </article>
        </div>
      ) : null}
    </section>
  );
}
