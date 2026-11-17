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
import type { MetricSample } from "../../lib/types";
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

function formatWhen(iso: string | null): string {
  if (!iso) return "Never recorded";
  try {
    return new Date(iso).toLocaleString([], {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function withNetRates(samples: MetricSample[]) {
  return samples.map((s, i) => {
    const prev = i > 0 ? samples[i - 1] : undefined;
    let rx_kbps = 0;
    let tx_kbps = 0;
    if (prev) {
      const dt = Math.max(
        1,
        (new Date(s.ts).getTime() - new Date(prev.ts).getTime()) / 1000,
      );
      rx_kbps = Math.max(0, (s.net_rx_bytes - prev.net_rx_bytes) / 1024 / dt);
      tx_kbps = Math.max(0, (s.net_tx_bytes - prev.net_tx_bytes) / 1024 / dt);
    }
    return {
      ...s,
      label: chartTick(s.ts),
      mem_mb: Math.round(s.mem_bytes / (1024 * 1024)),
      mem_limit_mb: Math.round(s.mem_limit_bytes / (1024 * 1024)),
      rx_kbps: Math.round(rx_kbps * 10) / 10,
      tx_kbps: Math.round(tx_kbps * 10) / 10,
    };
  });
}

function summarize(samples: ReturnType<typeof withNetRates>) {
  if (samples.length === 0) {
    return null;
  }
  const latest = samples[samples.length - 1]!;
  const peakPlayers = Math.max(...samples.map((s) => s.players_online));
  const peakCpu = Math.max(...samples.map((s) => s.cpu_pct));
  const peakMem = Math.max(...samples.map((s) => s.mem_mb));
  const avgCpu = samples.reduce((sum, s) => sum + s.cpu_pct, 0) / samples.length;
  return {
    latest,
    peakPlayers,
    peakCpu,
    peakMem,
    avgCpu,
  };
}

export function MetricsPage() {
  const query = useQuery({
    queryKey: ["metrics-overview"],
    queryFn: () => fetchMetricsOverview(24, 7),
    refetchInterval: 30_000,
  });

  const data = query.data;
  const samples = withNetRates(downsample(data?.samples ?? [], 120));
  const summary = summarize(samples);
  const joinsTotal = (data?.joins ?? []).reduce((sum, j) => sum + j.joins, 0);
  const playtimeTotal = (data?.playtime ?? []).reduce((sum, p) => sum + p.seconds, 0);

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

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Players now"
            value={String(summary.latest.players_online)}
            hint={`Peak ${summary.peakPlayers} in window`}
          />
          <StatCard
            label="CPU now"
            value={`${summary.latest.cpu_pct.toFixed(1)}%`}
            hint={`Peak ${summary.peakCpu.toFixed(1)}% · avg ${summary.avgCpu.toFixed(1)}%`}
          />
          <StatCard
            label="Memory now"
            value={`${summary.latest.mem_mb} MB`}
            hint={
              summary.latest.mem_limit_mb > 0
                ? `Peak ${summary.peakMem} MB · limit ${summary.latest.mem_limit_mb} MB`
                : `Peak ${summary.peakMem} MB`
            }
          />
          <StatCard
            label="Joins (7d)"
            value={String(joinsTotal)}
            hint={`${formatHours(playtimeTotal)} total playtime`}
          />
        </div>
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

          <ChartCard title="Network (KB/s)">
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
                  dataKey="rx_kbps"
                  stroke="var(--color-primary)"
                  fill="var(--color-primary)"
                  fillOpacity={0.15}
                  name="RX KB/s"
                />
                <Area
                  type="monotone"
                  dataKey="tx_kbps"
                  stroke="var(--color-accent)"
                  fill="var(--color-accent)"
                  fillOpacity={0.12}
                  name="TX KB/s"
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
              <div className="max-h-72 overflow-y-auto rounded-md border border-border">
                <ul className="divide-y divide-border">
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
              </div>
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
              <div className="max-h-72 overflow-y-auto rounded-md border border-border">
                <ul className="divide-y divide-border">
                  {data.disk.worlds.map((w) => (
                    <li
                      key={w.folder_name}
                      className="flex items-start justify-between gap-3 px-4 py-3 text-sm"
                    >
                      <div className="min-w-0 space-y-1">
                        <p className="truncate">
                          {w.display_name}
                          {w.is_active ? (
                            <span className="ml-2 text-xs text-primary">active</span>
                          ) : null}
                        </p>
                        <p className="text-xs text-muted">
                          Last played: {formatWhen(w.last_played_at)}
                        </p>
                        {(w.gamemode || w.difficulty) && (
                          <p className="text-xs text-muted">
                            {[w.gamemode, w.difficulty].filter(Boolean).join(" · ")}
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 text-muted">
                        {formatBytes(w.size_bytes)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {data && data.backups.length > 0 ? (
        <div className="space-y-3">
          <h2 className="font-pixel text-lg">Recent backups</h2>
          <div className="max-h-72 overflow-y-auto rounded-md border border-border">
            <ul className="divide-y divide-border">
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
                      {b.created_at ? ` · ${formatWhen(b.created_at)}` : ""}
                    </span>
                  </li>
                ))}
            </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="mf-card px-4 py-3 space-y-1">
      <p className="text-xs text-muted">{label}</p>
      <p className="font-pixel text-xl text-primary">{value}</p>
      <p className="text-xs text-muted">{hint}</p>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mf-card p-4 space-y-3">
      <h2 className="text-sm text-muted">{title}</h2>
      <div className="h-[220px] w-full">{children}</div>
    </div>
  );
}
