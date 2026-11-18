import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { APP_DISPLAY_NAME } from "../../app/constants";
import { Icon, Icons } from "../../components/icons";
import { Skeleton } from "../../components/ui/Skeleton";
import {
  fetchMetricsDashboard,
  fetchServerStatus,
  fetchStreamStatus,
} from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import { formatBytes, formatHours } from "../metrics/format";
import { ContainerActivity } from "../server/ContainerActivity";

function formatUptime(seconds: number | null): string {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function HomePage() {
  const { user } = useAuth();
  const statusQuery = useQuery({
    queryKey: ["server-status"],
    queryFn: fetchServerStatus,
    refetchInterval: 10_000,
  });
  const metricsQuery = useQuery({
    queryKey: ["metrics-dashboard"],
    queryFn: fetchMetricsDashboard,
    refetchInterval: 30_000,
  });
  const streamQuery = useQuery({
    queryKey: ["stream-status"],
    queryFn: fetchStreamStatus,
    refetchInterval: 10_000,
    retry: false,
  });

  const status = statusQuery.data;
  const running = status?.container.running;
  const metrics = metricsQuery.data;
  const latest = metrics?.latest;
  const streamLive = Boolean(streamQuery.data?.live && streamQuery.data.enabled);

  return (
    <section className="space-y-6">
      <div className="space-y-2 page-enter">
        <h1 className="font-pixel text-2xl text-primary mf-title-glow">Dashboard</h1>
        <p className="max-w-xl text-muted leading-relaxed">
          Welcome{user ? `, ${user.username}` : ""}. {APP_DISPLAY_NAME} server overview.
        </p>
      </div>

      {streamLive ? (
        <Link
          to="/stream"
          className="mf-card block p-4 transition-colors hover:bg-border/30"
        >
          <p className="inline-flex items-center gap-2 text-sm text-danger">
            <span className="mf-status-pulse h-2.5 w-2.5 rounded-full bg-danger" />
            Live now
          </p>
          <p className="mt-1 font-pixel text-xl text-primary">Watch</p>
          <p className="mt-1 text-xs text-muted truncate">
            {streamQuery.data?.title ?? "Stream"} · {streamQuery.data?.viewers ?? 0}{" "}
            watching
          </p>
        </Link>
      ) : null}

      <ContainerActivity
        status={statusQuery.data}
        loading={statusQuery.isLoading}
        compact
      />

      <div className="grid gap-4 sm:grid-cols-3 stagger-children">
        <MetricTile icon={Icons.Status} label="Status" loading={statusQuery.isLoading}>
          <p
            className={`mt-1 font-pixel text-xl inline-flex items-center gap-2 ${
              running ? "text-primary" : ""
            }`}
          >
            {running ? (
              <span className="mf-status-pulse h-2.5 w-2.5 rounded-full bg-primary" />
            ) : null}
            {running ? "Online" : status?.container.exists ? "Offline" : "No container"}
          </p>
        </MetricTile>
        <MetricTile icon={Icons.Worlds} label="World" loading={statusQuery.isLoading}>
          <p className="mt-1 font-pixel text-xl truncate">
            {status?.level_name ?? "—"}
          </p>
        </MetricTile>
        <MetricTile
          icon={Icons.Players}
          label="Players"
          loading={statusQuery.isLoading}
        >
          <p className="mt-1 font-pixel text-xl">{status?.player_count ?? 0}</p>
          <p className="text-xs text-muted mt-1">
            Uptime {formatUptime(status?.container.uptime_seconds ?? null)}
          </p>
        </MetricTile>
      </div>

      <div className="grid gap-4 sm:grid-cols-3 stagger-children">
        <MetricTile icon={Icons.Cpu} label="CPU" loading={metricsQuery.isLoading}>
          <p className="mt-1 font-pixel text-xl">
            {latest ? `${latest.cpu_pct.toFixed(1)}%` : "—"}
          </p>
        </MetricTile>
        <MetricTile icon={Icons.Memory} label="Memory" loading={metricsQuery.isLoading}>
          <p className="mt-1 font-pixel text-xl">
            {latest ? formatBytes(latest.mem_bytes) : "—"}
          </p>
        </MetricTile>
        <MetricTile icon={Icons.Disk} label="Disk" loading={metricsQuery.isLoading}>
          <p className="mt-1 font-pixel text-xl truncate">
            {formatBytes(
              (metrics?.disk.worlds_bytes ?? 0) + (metrics?.disk.backups_bytes ?? 0),
            )}
          </p>
        </MetricTile>
      </div>

      {metrics && metrics.playtime_week.length > 0 ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg">Playtime this week</h2>
            <Link
              className="text-sm text-accent underline-offset-2 hover:underline"
              to="/metrics"
            >
              All metrics
            </Link>
          </div>
          <ul className="text-sm text-muted space-y-1">
            {metrics.playtime_week.map((p) => (
              <li key={p.gamertag} className="flex justify-between gap-3">
                <span className="truncate text-text">{p.gamertag}</span>
                <span>{formatHours(p.seconds)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {metrics?.world_insight?.available ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg">World content</h2>
            <Link
              className="text-sm text-accent underline-offset-2 hover:underline"
              to="/metrics"
            >
              Deep scan
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricTile icon={Icons.Packs} label="Packs">
              <p className="mt-1 font-pixel text-xl">
                {metrics.world_insight.totals.packs ?? 0}
              </p>
              <p className="text-xs text-muted mt-1">
                {(metrics.world_insight.categories.weapons_combat ?? 0) +
                  (metrics.world_insight.categories.structures_builds ?? 0)}{" "}
                weapons/builds packs
              </p>
            </MetricTile>
            <MetricTile icon={Icons.Items} label="Items · entities">
              <p className="mt-1 font-pixel text-xl">
                {metrics.world_insight.totals.items ?? 0} ·{" "}
                {metrics.world_insight.totals.entities ?? 0}
              </p>
              <p className="text-xs text-muted mt-1">
                {metrics.world_insight.totals.structures ?? 0} structures ·{" "}
                {metrics.world_insight.totals.weapon_like_items ?? 0} weapon-like
              </p>
            </MetricTile>
            <MetricTile icon={Icons.Seed} label="Seed">
              <p className="mt-1 font-pixel text-sm truncate">
                {String(metrics.world_insight.level?.seed ?? "—")}
              </p>
              <p className="text-xs text-muted mt-1">
                DB {formatBytes(Number(metrics.world_insight.world?.db_bytes ?? 0))}
              </p>
            </MetricTile>
          </div>
        </div>
      ) : null}

      {metrics?.login_activity && metrics.login_activity.recent.length > 0 ? (
        <div className="space-y-2">
          <h2 className="text-lg inline-flex items-center gap-2">
            <Icon icon={Icons.Login} size={18} className="text-primary" />
            Recent panel logins
          </h2>
          <ul className="text-sm text-muted space-y-1">
            {metrics.login_activity.recent.slice(0, 5).map((row) => (
              <li
                key={`${row.ts}-${row.username}`}
                className="flex justify-between gap-3"
              >
                <span className="truncate text-text">{row.username}</span>
                <span className="shrink-0">
                  {new Date(row.ts).toLocaleString([], {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {status && status.players_online.length > 0 ? (
        <div>
          <h2 className="text-lg mb-2">Online now</h2>
          <ul className="text-sm text-muted space-y-1">
            {status.players_online.map((p) => (
              <li key={`${p.gamertag}-${p.joined_at}`}>{p.gamertag}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <ul className="grid gap-2 sm:grid-cols-2 text-sm">
        {(
          [
            { to: "/metrics", label: "Metrics", icon: Icons.Metrics },
            { to: "/stream", label: "Stream", icon: Icons.Stream },
            { to: "/worlds", label: "Worlds", icon: Icons.Worlds },
            { to: "/addons", label: "Add-ons", icon: Icons.Addons },
            { to: "/backups", label: "Backups", icon: Icons.Backups },
            ...(user?.role === "admin"
              ? [
                  { to: "/server", label: "Server controls", icon: Icons.Server },
                  { to: "/console", label: "Live console", icon: Icons.Console },
                  { to: "/users", label: "Manage users", icon: Icons.Users },
                ]
              : []),
            { to: "/account", label: "Account settings", icon: Icons.Account },
          ] as const
        ).map((item) => (
          <li key={item.to}>
            <Link
              className="mf-card flex min-h-11 items-center gap-2 px-3 py-2 text-text hover:text-primary"
              to={item.to}
            >
              <Icon icon={item.icon} size={16} className="text-primary" />
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function MetricTile({
  icon,
  label,
  loading,
  children,
}: {
  icon: LucideIcon;
  label: string;
  loading?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="mf-card p-4">
      <p className="inline-flex items-center gap-2 text-sm text-muted">
        <Icon icon={icon} size={15} className="text-primary" />
        {label}
      </p>
      {loading ? <Skeleton className="mt-2 h-7 w-24" /> : children}
    </div>
  );
}
