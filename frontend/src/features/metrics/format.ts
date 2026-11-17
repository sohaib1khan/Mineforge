export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatHours(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

export function downsample<T>(items: T[], maxPoints: number): T[] {
  if (items.length <= maxPoints) return items;
  const step = Math.ceil(items.length / maxPoints);
  const out: T[] = [];
  for (let i = 0; i < items.length; i += step) {
    const item = items[i];
    if (item !== undefined) out.push(item);
  }
  const last = items[items.length - 1];
  if (last !== undefined && out[out.length - 1] !== last) {
    out.push(last);
  }
  return out;
}
