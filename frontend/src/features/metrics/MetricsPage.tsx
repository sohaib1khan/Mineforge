import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "../../components/ui/EmptyState";
import { SkeletonLines } from "../../components/ui/Skeleton";
import { fetchMetricsOverview } from "../../lib/api";
import { downsample, formatBytes, formatHours } from "./format";

function chartTick(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function MetricsPage() {
  const query = useQuery({
    queryKey: ["metrics-overview"],
    queryFn: () => fetchMetricsOverview(24, 7),
    refetchInterval: 30_000,
  });

  const data = query.data;
  const samples = downsample(data?.samples ?? [], 120).map((s) => ({
    ...s,
    label: chartTick(s.ts),
    mem_mb: Math.round(s.mem_bytes / (1024 * 1024)),
  }));

  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h1 className="font-pixel text-2xl text-text">Metrics</h1>
        <p className="max-w-xl text-muted leading-relaxed">
          Players, playtime, and Bedrock container CPU/RAM sampled about every{" "}
          {data?.sample_interval_seconds ?? 30}s (kept {data?.retention_days ?? 30}{" "}
          days).
        </p>
      </div>

      {query.isLoading ? <SkeletonLines count={6} /> : null}
      {query.isError ? (
        <p className="text-sm text-danger" role="alert">
          Could not load metrics.
        </p>
      ) : null}

      {data && samples.length === 0 ? (
        <EmptyState
          title="No samples yet"
          description="Stats appear after the first sample (about 30 seconds once the scheduler is running)."
        />
      ) : null}

      {data && samples.length > 0 ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard title="Players online">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={samples}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "var(--color-muted)", fontSize: 11 }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "var(--color-muted)", fontSize: 11 }}
                  width={32}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="players_online"
                  stroke="var(--color-primary)"
                  fill="var(--color-primary)"
                  fillOpacity={0.25}
                  name="Players"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="CPU %">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={samples}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "var(--color-muted)", fontSize: 11 }}
                />
                <YAxis tick={{ fill: "var(--color-muted)", fontSize: 11 }} width={40} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="cpu_pct"
                  stroke="var(--color-accent)"
                  fill="var(--color-accent)"
                  fillOpacity={0.2}
                  name="CPU %"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Memory (MB)">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={samples}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "var(--color-muted)", fontSize: 11 }}
                />
                <YAxis tick={{ fill: "var(--color-muted)", fontSize: 11 }} width={48} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="mem_mb"
                  stroke="var(--color-warning)"
                  fill="var(--color-warning)"
                  fillOpacity={0.2}
                  name="Memory MB"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Joins per day">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.joins}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="day"
                  tick={{ fill: "var(--color-muted)", fontSize: 10 }}
                  tickFormatter={(v: string) => v.slice(5)}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "var(--color-muted)", fontSize: 11 }}
                  width={28}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-text)",
                  }}
                />
                <Bar dataKey="joins" fill="var(--color-primary)" name="Joins" />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      ) : null}

      {data ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-3">
            <h2 className="font-pixel text-lg">Playtime (7 days)</h2>
            {data.playtime.length === 0 ? (
              <p className="text-sm text-muted">No sessions in this window.</p>
            ) : (
              <ul className="divide-y divide-border rounded-md border border-border">
                {data.playtime.map((p) => (
                  <li
                    key={p.gamertag}
                    className="flex items-center justify-between gap-3 px-4 py-3 text-sm"
                  >
                    <span className="truncate">{p.gamertag}</span>
                    <span className="font-pixel text-primary">
                      {formatHours(p.seconds)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-3">
            <h2 className="font-pixel text-lg">Disk</h2>
            <p className="text-sm text-muted">
              Worlds {formatBytes(data.disk.worlds_bytes)} · Backups{" "}
              {formatBytes(data.disk.backups_bytes)} ({data.disk.backup_count} archives)
            </p>
            {data.disk.worlds.length === 0 ? (
              <p className="text-sm text-muted">No worlds tracked yet.</p>
            ) : (
              <ul className="divide-y divide-border rounded-md border border-border">
                {data.disk.worlds.map((w) => (
                  <li
                    key={w.folder_name}
                    className="flex items-center justify-between gap-3 px-4 py-3 text-sm"
                  >
                    <span className="truncate">
                      {w.display_name}
                      {w.is_active ? (
                        <span className="ml-2 text-xs text-primary">active</span>
                      ) : null}
                    </span>
                    <span className="text-muted">{formatBytes(w.size_bytes)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}

      {data && data.backups.length > 0 ? (
        <div className="space-y-3">
          <h2 className="font-pixel text-lg">Recent backups</h2>
          <ul className="divide-y divide-border rounded-md border border-border">
            {data.backups
              .slice()
              .reverse()
              .slice(0, 12)
              .map((b) => (
                <li
                  key={b.id}
                  className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"
                >
                  <span className="truncate">
                    {b.world_folder} <span className="text-muted">· {b.kind}</span>
                  </span>
                  <span className="text-muted">
                    {formatBytes(b.size_bytes)}
                    {b.verified ? " · verified" : ""}
                  </span>
                </li>
              ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-surface/70 p-4 space-y-3">
      <h2 className="text-sm text-muted">{title}</h2>
      <div className="h-[220px] w-full">{children}</div>
    </div>
  );
}
