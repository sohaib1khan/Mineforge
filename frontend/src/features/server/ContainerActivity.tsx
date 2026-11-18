import { Link } from "react-router-dom";

import { Icon, Icons } from "../../components/icons";
import { Skeleton } from "../../components/ui/Skeleton";
import type { ServerStatusResponse } from "../../lib/types";
import { formatBytes } from "../metrics/format";

type Props = {
  status: ServerStatusResponse | undefined;
  loading?: boolean;
  compact?: boolean;
};

function formatUptime(seconds: number | null): string {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function healthTone(health: string | null | undefined, running: boolean): string {
  if (!running) return "text-muted";
  const h = (health || "").toLowerCase();
  if (h === "healthy") return "text-primary";
  if (h === "unhealthy") return "text-danger";
  if (h === "starting") return "text-warning";
  return "text-accent";
}

export function ContainerActivity({ status, loading, compact }: Props) {
  if (loading && !status) {
    return (
      <div className="mf-card space-y-3 p-4">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }

  if (!status) return null;

  const c = status.container;
  const res = status.resources;
  const warnings = status.warnings ?? [];
  const ports = status.ports ?? [];
  const mounts = status.mounts ?? [];
  const envEntries = Object.entries(status.safe_env ?? {}).sort(([a], [b]) =>
    a.localeCompare(b),
  );
  const settingEntries = Object.entries(status.server_settings ?? {}).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return (
    <div className="mf-card space-y-4 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1 min-w-0">
          <h2 className="font-pixel text-lg inline-flex items-center gap-2">
            <Icon icon={Icons.Server} size={18} className="text-primary" />
            Bedrock container
          </h2>
          <p className="text-xs text-muted truncate">
            {c.name}
            {c.image ? ` · ${c.image}` : ""}
          </p>
        </div>
        <p
          className={`inline-flex items-center gap-2 text-sm capitalize ${healthTone(
            c.health,
            c.running,
          )}`}
        >
          {c.running ? (
            <span className="mf-status-pulse h-2.5 w-2.5 rounded-full bg-primary" />
          ) : (
            <Icon icon={Icons.Offline} size={14} />
          )}
          {c.status}
          {c.health ? ` · ${c.health}` : ""}
        </p>
      </div>

      {warnings.length > 0 ? (
        <ul className="space-y-1 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
          {warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      ) : null}

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
        <div>
          <dt className="text-muted inline-flex items-center gap-1.5">
            <Icon icon={Icons.Timer} size={14} />
            Uptime
          </dt>
          <dd className="font-pixel text-text">{formatUptime(c.uptime_seconds)}</dd>
        </div>
        <div>
          <dt className="text-muted inline-flex items-center gap-1.5">
            <Icon icon={Icons.Cpu} size={14} />
            CPU
          </dt>
          <dd className="font-pixel text-text">
            {res ? `${res.cpu_pct.toFixed(1)}%` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted inline-flex items-center gap-1.5">
            <Icon icon={Icons.Memory} size={14} />
            Memory
          </dt>
          <dd className="font-pixel text-text">
            {res
              ? `${formatBytes(res.mem_bytes)}${
                  res.mem_pct != null ? ` (${res.mem_pct}%)` : ""
                }`
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted inline-flex items-center gap-1.5">
            <Icon icon={Icons.Players} size={14} />
            Players
          </dt>
          <dd className="font-pixel text-text">{status.player_count}</dd>
        </div>
      </dl>

      {!compact ? (
        <>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">PID · restarts</dt>
              <dd className="text-text">
                {c.pid ?? "—"} · {c.restart_count}
                {c.restart_policy ? ` (${c.restart_policy})` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Exit · OOM</dt>
              <dd className="text-text">
                {c.exit_code ?? "—"} · {c.oom_killed ? "yes" : "no"}
              </dd>
            </div>
            <div>
              <dt className="text-muted">World (level-name)</dt>
              <dd className="truncate text-text">{status.level_name ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted">Network I/O</dt>
              <dd className="text-text">
                {res
                  ? `↓ ${formatBytes(res.net_rx_bytes)} · ↑ ${formatBytes(res.net_tx_bytes)}`
                  : "—"}
              </dd>
            </div>
          </dl>

          {ports.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs text-muted">Published ports</p>
              <ul className="flex flex-wrap gap-2 text-xs">
                {ports.map((p) => (
                  <li
                    key={`${p.private}-${p.public ?? "none"}`}
                    className="rounded-md border border-border px-2 py-1 text-text"
                  >
                    {p.private}
                    {p.public ? ` → ${p.public}` : " (unpublished)"}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {mounts.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs text-muted">Mounts</p>
              <ul className="space-y-1 text-xs text-muted">
                {mounts.map((m) => (
                  <li key={m.destination} className="truncate">
                    <span className="text-text">{m.destination}</span>
                    {m.type ? ` · ${m.type}` : ""}
                    {m.mode ? ` · ${m.mode}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {settingEntries.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs text-muted">server.properties (live)</p>
              <dl className="grid gap-1 text-xs sm:grid-cols-2">
                {settingEntries.map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-2">
                    <dt className="text-muted truncate">{key}</dt>
                    <dd className="truncate text-text font-mono">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}

          {envEntries.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs text-muted">Container env (safe keys)</p>
              <dl className="grid gap-1 text-xs sm:grid-cols-2">
                {envEntries.map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-2">
                    <dt className="text-muted truncate">{key}</dt>
                    <dd className="truncate text-text font-mono">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}

          <p className="text-xs text-muted">
            Live console stream:{" "}
            <Link
              className="text-accent underline-offset-2 hover:underline"
              to="/console"
            >
              open Console
            </Link>
          </p>
        </>
      ) : (
        <p className="text-xs text-muted">
          <Link className="text-accent underline-offset-2 hover:underline" to="/server">
            Full container details
          </Link>
          {" · "}
          <Link
            className="text-accent underline-offset-2 hover:underline"
            to="/console"
          >
            Console
          </Link>
        </p>
      )}
    </div>
  );
}
