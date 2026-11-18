import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Icon, Icons } from "../../components/icons";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { useToast } from "../../components/ui/Toast";
import {
  ApiError,
  addAllowlist,
  applyPublicIp,
  detectPublicIp,
  fetchAllowlist,
  fetchNetworkStatus,
  fetchPermissions,
  fetchProperties,
  fetchServerStatus,
  fetchVersionInfo,
  removeAllowlist,
  serverAction,
  setPermission,
  updateProperties,
} from "../../lib/api";
import type { NetworkStatusResponse } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";
import { ContainerActivity } from "./ContainerActivity";

export function ServerPage() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [allowName, setAllowName] = useState("");
  const [opXuid, setOpXuid] = useState("");
  const [opName, setOpName] = useState("");
  const [draftProps, setDraftProps] = useState<Record<string, string>>({});
  const [manualIp, setManualIp] = useState("");
  const [networkPreview, setNetworkPreview] = useState<NetworkStatusResponse | null>(
    null,
  );

  const statusQuery = useQuery({
    queryKey: ["server-status"],
    queryFn: fetchServerStatus,
    refetchInterval: 8_000,
  });
  const propsQuery = useQuery({
    queryKey: ["server-properties"],
    queryFn: async () => {
      const data = await fetchProperties();
      setDraftProps(data.values);
      return data;
    },
  });
  const allowQuery = useQuery({ queryKey: ["allowlist"], queryFn: fetchAllowlist });
  const permsQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: fetchPermissions,
  });
  const networkQuery = useQuery({
    queryKey: ["server-network"],
    queryFn: fetchNetworkStatus,
  });
  const versionQuery = useQuery({
    queryKey: ["server-version"],
    queryFn: fetchVersionInfo,
  });

  const actionMutation = useMutation({
    mutationFn: serverAction,
    onSuccess: async (_, action) => {
      setMessage(`Server ${action} requested.`);
      setError(null);
      toast.push(`Server ${action} requested.`, "info");
      await queryClient.invalidateQueries({ queryKey: ["server-status"] });
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Action failed");
    },
  });

  if (user?.role !== "admin") {
    return <p className="text-danger">Admin access required.</p>;
  }

  const running = statusQuery.data?.container.running;
  const network = networkPreview ?? networkQuery.data;

  async function onSaveProps(event: FormEvent) {
    event.preventDefault();
    const original = propsQuery.data?.values ?? {};
    const updates: Record<string, string> = {};
    for (const item of propsQuery.data?.catalog ?? []) {
      if (!item.editable) continue;
      const next = draftProps[item.key];
      if (next != null && next !== original[item.key]) {
        updates[item.key] = next;
      }
    }
    if (Object.keys(updates).length === 0) {
      setMessage("No property changes.");
      return;
    }
    try {
      const saved = await updateProperties(updates);
      setDraftProps(saved.values);
      setMessage("Properties saved. Restart the server for some keys to apply.");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["server-properties"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    }
  }

  return (
    <section className="space-y-8">
      <div className="space-y-1">
        <h1 className="font-pixel text-2xl inline-flex items-center gap-2">
          <Icon icon={Icons.Server} size={22} className="text-primary" />
          Server
        </h1>
        <p className="text-sm text-muted">
          Live Docker + Bedrock view for{" "}
          <span className="text-text">
            {statusQuery.data?.container.name ?? "bedrock"}
          </span>
          . Polls about every 8s while this page is open.
        </p>
      </div>

      <ContainerActivity status={statusQuery.data} loading={statusQuery.isLoading} />

      <div className="flex flex-wrap gap-2">
        <Button
          className="gap-2"
          disabled={actionMutation.isPending || running}
          onClick={() => actionMutation.mutate("start")}
        >
          <Icon icon={Icons.Status} size={16} />
          Start
        </Button>
        <Button
          variant="secondary"
          className="gap-2"
          disabled={actionMutation.isPending || !running}
          onClick={() => actionMutation.mutate("stop")}
        >
          <Icon icon={Icons.Offline} size={16} />
          Stop
        </Button>
        <Button
          variant="secondary"
          disabled={actionMutation.isPending || !statusQuery.data?.container.exists}
          onClick={() => actionMutation.mutate("restart")}
        >
          Restart
        </Button>
      </div>

      {error ? (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="text-sm text-primary">{message}</p> : null}

      <div className="space-y-3 rounded-md border border-border bg-surface/70 p-4">
        <h2 className="text-lg">Version</h2>
        {versionQuery.isLoading ? (
          <p className="text-sm text-muted">Loading version…</p>
        ) : (
          <>
            <p className="text-sm">
              Image:{" "}
              <span className="text-text">{versionQuery.data?.image ?? "—"}</span>
            </p>
            <p className="text-sm">
              VERSION env:{" "}
              <span className="font-pixel text-text">
                {versionQuery.data?.version_env ?? "unset"}
              </span>{" "}
              {versionQuery.data?.pinned ? (
                <span className="text-xs text-primary">(pinned)</span>
              ) : (
                <span className="text-xs text-warning">(not pinned)</span>
              )}
            </p>
            <p className="text-sm text-muted leading-relaxed">
              {versionQuery.data?.guidance}
            </p>
            <p className="text-sm">
              <Link
                className="text-accent underline-offset-2 hover:underline"
                to="/help"
              >
                Version matching guide
              </Link>
            </p>
          </>
        )}
      </div>

      <div className="space-y-4 rounded-md border border-border bg-surface/70 p-4">
        <div className="space-y-1">
          <h2 className="text-lg">Network (NetherNet)</h2>
          <p className="text-sm text-muted leading-relaxed">
            Transport {network?.transport ?? "nethernet"} · TCP{" "}
            {network?.server_port ?? "19132"} · UDP{" "}
            {network?.udp_range ?? "19140-19155"}
          </p>
        </div>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">Advertised public IP</dt>
            <dd className="font-pixel text-text">
              {network?.advertised_public_ip ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-muted">server-udp-ports</dt>
            <dd className="break-all text-text">{network?.server_udp_ports ?? "—"}</dd>
          </div>
          {network?.detected_public_ip ? (
            <div>
              <dt className="text-muted">Detected public IP</dt>
              <dd className="font-pixel text-text">{network.detected_public_ip}</dd>
            </div>
          ) : null}
          {network?.proposed_server_udp_ports ? (
            <div>
              <dt className="text-muted">Proposed value</dt>
              <dd className="break-all text-text">
                {network.proposed_server_udp_ports}
              </dd>
            </div>
          ) : null}
        </dl>
        <p className="text-xs text-muted leading-relaxed">{network?.note}</p>

        <div className="flex flex-wrap items-end gap-2">
          <Input
            label="Manual IPv4 (optional)"
            name="manual_ip"
            value={manualIp}
            onChange={(e) => setManualIp(e.target.value)}
            placeholder="203.0.113.10"
          />
          <Button
            variant="secondary"
            onClick={async () => {
              try {
                const data = await detectPublicIp();
                setNetworkPreview(data);
                setMessage(
                  `Detected ${data.detected_public_ip ?? "unknown"}. Review, then apply.`,
                );
                setError(null);
              } catch (err) {
                setError(err instanceof ApiError ? err.message : "Detect failed");
              }
            }}
          >
            Detect public IP
          </Button>
          <Button
            onClick={async () => {
              try {
                const data = await applyPublicIp({
                  ip_address: manualIp.trim() || undefined,
                  restart: true,
                });
                setNetworkPreview(data);
                setManualIp("");
                setMessage(
                  `Updated server-udp-ports${data.restarted ? " and restarted Bedrock" : ""}.`,
                );
                setError(null);
                toast.push("Public IP applied.", "success");
                await queryClient.invalidateQueries({
                  queryKey: ["server-network"],
                });
                await queryClient.invalidateQueries({
                  queryKey: ["server-properties"],
                });
                await queryClient.invalidateQueries({
                  queryKey: ["server-status"],
                });
              } catch (err) {
                setError(err instanceof ApiError ? err.message : "Apply failed");
                toast.push(
                  err instanceof ApiError ? err.message : "Apply failed",
                  "error",
                );
              }
            }}
          >
            Re-detect & apply
          </Button>
        </div>

        <div className="space-y-2">
          <h3 className="text-sm text-muted">Forwarding checklist</h3>
          <ul className="space-y-2 text-sm">
            {(network?.checklist ?? []).map((item) => (
              <li key={item.id} className="rounded border border-border/70 px-3 py-2">
                <p className="font-medium text-text">{item.title}</p>
                <p className="text-muted">{item.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <form className="space-y-4" onSubmit={onSaveProps}>
        <h2 className="text-lg">server.properties</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {(propsQuery.data?.catalog ?? []).map((item) => (
            <label key={item.key} className="block space-y-1">
              <span className="text-sm text-muted">
                {item.key}
                {!item.editable ? " (read-only)" : ""}
              </span>
              <p className="text-xs text-muted/80">{item.description}</p>
              {item.value_type === "enum" && item.allowed_values ? (
                <select
                  className="min-h-11 w-full rounded-md border border-border bg-surface px-3"
                  disabled={!item.editable}
                  value={draftProps[item.key] ?? ""}
                  onChange={(e) =>
                    setDraftProps((prev) => ({
                      ...prev,
                      [item.key]: e.target.value,
                    }))
                  }
                >
                  {item.allowed_values.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="min-h-11 w-full rounded-md border border-border bg-surface px-3"
                  disabled={!item.editable}
                  value={draftProps[item.key] ?? ""}
                  onChange={(e) =>
                    setDraftProps((prev) => ({
                      ...prev,
                      [item.key]: e.target.value,
                    }))
                  }
                />
              )}
            </label>
          ))}
        </div>
        <Button type="submit">Save properties</Button>
      </form>

      <div className="space-y-3">
        <h2 className="text-lg">Allowlist</h2>
        <form
          className="flex flex-wrap gap-2 items-end"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await addAllowlist(allowName);
              setAllowName("");
              await queryClient.invalidateQueries({ queryKey: ["allowlist"] });
              setMessage("Allowlist updated.");
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Allowlist failed");
            }
          }}
        >
          <Input
            label="Gamertag"
            name="allow_name"
            value={allowName}
            onChange={(e) => setAllowName(e.target.value)}
            required
          />
          <Button type="submit">Add</Button>
        </form>
        <ul className="text-sm space-y-2">
          {(allowQuery.data?.entries ?? []).map((entry) => {
            const name = String(entry.name ?? "");
            return (
              <li
                key={name}
                className="flex items-center justify-between gap-2 border-b border-border/60 py-2"
              >
                <span>{name}</span>
                <Button
                  variant="danger"
                  onClick={async () => {
                    try {
                      await removeAllowlist(name);
                      await queryClient.invalidateQueries({
                        queryKey: ["allowlist"],
                      });
                    } catch (err) {
                      setError(err instanceof ApiError ? err.message : "Remove failed");
                    }
                  }}
                >
                  Remove
                </Button>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="space-y-3">
        <h2 className="text-lg">Operators / permissions</h2>
        <form
          className="grid gap-2 sm:grid-cols-3 items-end"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await setPermission({
                xuid: opXuid,
                permission: "operator",
                name: opName || undefined,
              });
              setOpXuid("");
              setOpName("");
              await queryClient.invalidateQueries({ queryKey: ["permissions"] });
              setMessage("Permission saved.");
            } catch (err) {
              setError(err instanceof ApiError ? err.message : "Permission failed");
            }
          }}
        >
          <Input
            label="XUID"
            name="op_xuid"
            value={opXuid}
            onChange={(e) => setOpXuid(e.target.value)}
            required
          />
          <Input
            label="Name (optional)"
            name="op_name"
            value={opName}
            onChange={(e) => setOpName(e.target.value)}
          />
          <Button type="submit">Set operator</Button>
        </form>
        <ul className="text-sm space-y-1 text-muted">
          {(permsQuery.data?.entries ?? []).map((entry) => (
            <li key={String(entry.xuid)}>
              {String(entry.name ?? entry.xuid)} — {String(entry.permission)}
            </li>
          ))}
        </ul>
        <Select label="Quick note" name="note" disabled defaultValue="tip">
          <option value="tip">op / give require the player to be online</option>
        </Select>
      </div>
    </section>
  );
}
