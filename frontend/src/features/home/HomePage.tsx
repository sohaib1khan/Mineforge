import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { APP_DISPLAY_NAME } from "../../app/constants";
import { Skeleton } from "../../components/ui/Skeleton";
import {
  fetchMetricsDashboard,
  fetchServerStatus,
  fetchStreamStatus,
} from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import { formatBytes, formatHours } from "../metrics/format";

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

      <div className="grid gap-4 sm:grid-cols-3 stagger-children">
        <div className="mf-card p-4">
          <p className="text-sm text-muted">Status</p>
          {statusQuery.isLoading ? (
            <Skeleton className="mt-2 h-7 w-24" />
          ) : (
            <p
              className={`mt-1 font-pixel text-xl inline-flex items-center gap-2 ${
                running ? "text-primary" : ""
              }`}
            >
              {running ? (
                <span className="mf-status-pulse h-2.5 w-2.5 rounded-full bg-primary" />
              ) : null}
              {running
                ? "Online"
                : status?.container.exists
                  ? "Offline"
                  : "No container"}
            </p>
          )}
        </div>
        <div className="mf-card p-4">
          <p className="text-sm text-muted">World</p>
          {statusQuery.isLoading ? (
            <Skeleton className="mt-2 h-7 w-32" />
          ) : (
            <p className="mt-1 font-pixel text-xl truncate">
              {status?.level_name ?? "—"}
            </p>
          )}
        </div>
        <div className="mf-card p-4">
          <p className="text-sm text-muted">Players</p>
          {statusQuery.isLoading ? (
            <Skeleton className="mt-2 h-7 w-16" />
          ) : (
            <>
              <p className="mt-1 font-pixel text-xl">{status?.player_count ?? 0}</p>
              <p className="text-xs text-muted mt-1">
                Uptime {formatUptime(status?.container.uptime_seconds ?? null)}
              </p>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3 stagger-children">
        <div className="mf-card p-4">
          <p className="text-sm text-muted">CPU</p>
          {metricsQuery.isLoading ? (
            <Skeleton className="mt-2 h-7 w-16" />
          ) : (
            <p className="mt-1 font-pixel text-xl">
              {latest ? `${latest.cpu_pct.toFixed(1)}%` : "—"}
            </p>
          )}
        </div>
        <div className="mf-card p-4">
          <p className="text-sm text-muted">Memory</p>
          {metricsQuery.isLoading ? (
            <Skeleton className="mt-2 h-7 w-20" />
          ) : (
            <p className="mt-1 font-pixel text-xl">
              {latest ? formatBytes(latest.mem_bytes) : "—"}
            </p>
          )}
        </div>
        <div className="mf-card p-4">
          <p className="text-sm text-muted">Disk</p>
          {metricsQuery.isLoading ? (
            <Skeleton className="mt-2 h-7 w-24" />
          ) : (
            <p className="mt-1 font-pixel text-xl truncate">
              {formatBytes(
                (metrics?.disk.worlds_bytes ?? 0) + (metrics?.disk.backups_bytes ?? 0),
              )}
            </p>
          )}
        </div>
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

      <ul className="space-y-2 text-sm">
        <li>
          <Link
            className="text-accent underline-offset-2 hover:underline"
            to="/metrics"
          >
            Metrics
          </Link>
        </li>
        <li>
          <Link className="text-accent underline-offset-2 hover:underline" to="/stream">
            Stream
          </Link>
        </li>
        <li>
          <Link className="text-accent underline-offset-2 hover:underline" to="/worlds">
            Worlds
          </Link>
        </li>
        <li>
          <Link className="text-accent underline-offset-2 hover:underline" to="/addons">
            Add-ons
          </Link>
        </li>
        <li>
          <Link
            className="text-accent underline-offset-2 hover:underline"
            to="/backups"
          >
            Backups
          </Link>
        </li>
        {user?.role === "admin" ? (
          <>
            <li>
              <Link
                className="text-accent underline-offset-2 hover:underline"
                to="/server"
              >
                Server controls
              </Link>
            </li>
            <li>
              <Link
                className="text-accent underline-offset-2 hover:underline"
                to="/console"
              >
                Live console
              </Link>
            </li>
            <li>
              <Link
                className="text-accent underline-offset-2 hover:underline"
                to="/users"
              >
                Manage users
              </Link>
            </li>
          </>
        ) : null}
        <li>
          <Link
            className="text-accent underline-offset-2 hover:underline"
            to="/account"
          >
            Account settings
          </Link>
        </li>
      </ul>
    </section>
  );
}
