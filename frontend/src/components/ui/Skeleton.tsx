type Props = {
  className?: string;
};

export function Skeleton({ className = "" }: Props) {
  return (
    <div
      className={`animate-pulse rounded-md bg-border/50 motion-safe:animate-pulse ${className}`}
      aria-hidden="true"
    />
  );
}

export function SkeletonLines({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className={`h-4 ${i === count - 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}
