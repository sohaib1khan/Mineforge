import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { Icon, Icons } from "../../components/icons";
import { EmptyState } from "../../components/ui/EmptyState";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { SkeletonLines } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/Toast";
import {
  cloneWorld,
  createWorld,
  deleteWorld,
  fetchWorlds,
  importWorld,
  renameWorld,
  resetWorld,
} from "../../lib/api";
import type { WorldResponse } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";
import { OperationDrawer } from "../operations/OperationDrawer";
import { SwitchDialog } from "./SwitchDialog";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
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

export function WorldsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [createName, setCreateName] = useState("");
  const [switchTarget, setSwitchTarget] = useState<WorldResponse | null>(null);
  const [operationId, setOperationId] = useState<number | null>(null);

  const listQuery = useQuery({
    queryKey: ["worlds"],
    queryFn: fetchWorlds,
    refetchInterval: operationId ? 4000 : 15_000,
  });

  const refresh = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["worlds"] });
    void queryClient.invalidateQueries({ queryKey: ["server-status"] });
    void queryClient.invalidateQueries({ queryKey: ["switch-status"] });
  }, [queryClient]);

  const createMutation = useMutation({
    mutationFn: () => createWorld({ display_name: createName }),
    onSuccess: () => {
      setCreateName("");
      setError(null);
      toast.push("World created.", "success");
      refresh();
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => importWorld({ file }),
    onSuccess: (data) => {
      setError(null);
      if (data.warnings.length) {
        const msg = `Imported with warnings: ${data.warnings.join(" ")}`;
        setError(msg);
        toast.push(msg, "info");
      } else {
        toast.push("World imported.", "success");
      }
      refresh();
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWorld,
    onSuccess: () => {
      setError(null);
      toast.push("World deleted.", "success");
      refresh();
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const resetMutation = useMutation({
    mutationFn: resetWorld,
    onSuccess: (data) => {
      setError(null);
      setOperationId(data.operation.id);
      toast.push("World reset started. A backup is taken first.", "info");
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const worlds = listQuery.data?.worlds ?? [];

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="font-pixel text-2xl text-text inline-flex items-center gap-2">
          <Icon icon={Icons.Worlds} size={22} className="text-primary" />
          Worlds
        </h1>
        <p className="max-w-xl text-muted leading-relaxed">
          Create or import adds a world <strong>next to</strong> your existing ones. Tap{" "}
          <strong>Switch</strong> when you want Bedrock to load it — MineForge backs up
          the current world first and rolls back if startup fails. Packs/mods from sites
          like MCPEDL go under <strong>Add-ons</strong>, not here.
        </p>
      </div>

      {isAdmin ? (
        <div className="mf-card space-y-4 p-4">
          <div className="space-y-1">
            <h2 className="text-sm font-medium text-text inline-flex items-center gap-2">
              <Icon icon={Icons.Status} size={16} className="text-primary" />
              Add a world
            </h2>
            <p className="text-xs text-muted">
              Create an empty world, or import a <code>.mcworld</code>. Neither removes
              your current worlds.
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <Input
              label="New world"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              placeholder="Display name"
            />
            <Button
              className="gap-2"
              onClick={() => createMutation.mutate()}
              disabled={!createName.trim() || createMutation.isPending}
            >
              <Icon icon={Icons.Worlds} size={16} />
              {createMutation.isPending ? "Creating…" : "Create world"}
            </Button>
            <Button
              variant="secondary"
              className="gap-2"
              onClick={() => fileRef.current?.click()}
              disabled={importMutation.isPending}
            >
              <Icon icon={Icons.Packs} size={16} />
              {importMutation.isPending ? "Importing…" : "Import .mcworld"}
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".mcworld,.zip"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) importMutation.mutate(file);
                e.target.value = "";
              }}
            />
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}

      {listQuery.isLoading ? (
        <SkeletonLines count={4} />
      ) : worlds.length === 0 ? (
        <EmptyState
          title="No worlds yet"
          description="Worlds appear when Bedrock has data on disk. Admins can create a world or import a .mcworld file."
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {worlds.map((w) => (
            <li key={w.id} className="mf-card p-4 space-y-3">
              <div className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="font-pixel text-lg truncate">{w.display_name}</h2>
                  {w.is_active ? (
                    <span className="text-xs text-primary">Active</span>
                  ) : null}
                </div>
                <p className="text-xs text-muted truncate">Folder: {w.folder_name}</p>
                <p className="text-xs text-muted">
                  Last played: {formatWhen(w.last_played_at)}
                </p>
                <p className="text-xs text-muted">
                  {formatBytes(w.size_bytes)}
                  {w.valid ? "" : " · incomplete"}
                  {!w.on_disk ? " · missing on disk" : ""}
                  {w.gamemode ? ` · ${w.gamemode}` : ""}
                  {w.difficulty ? ` · ${w.difficulty}` : ""}
                  {w.needs_experiments ? " · experiments" : ""}
                </p>
                {w.seed ? (
                  <p className="text-xs text-muted truncate">Seed: {w.seed}</p>
                ) : null}
                {w.description ? (
                  <p className="text-xs text-muted line-clamp-2">{w.description}</p>
                ) : null}
                {w.created_at ? (
                  <p className="text-xs text-muted">Added {formatWhen(w.created_at)}</p>
                ) : null}
                {w.warnings.length ? (
                  <p className="text-xs text-warning">{w.warnings[0]}</p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {!w.is_active ? (
                  <Button onClick={() => setSwitchTarget(w)} disabled={!w.on_disk}>
                    Switch
                  </Button>
                ) : null}
                {isAdmin ? (
                  <>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        const name = window.prompt("New display name", w.display_name);
                        if (!name) return;
                        void renameWorld(w.id, { display_name: name })
                          .then(() => refresh())
                          .catch((err: Error) => setError(err.message));
                      }}
                    >
                      Rename
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        const folder = window.prompt(
                          "Clone to folder name",
                          `${w.folder_name}_copy`,
                        );
                        if (!folder) return;
                        void cloneWorld(w.id, { folder_name: folder })
                          .then(() => refresh())
                          .catch((err: Error) => setError(err.message));
                      }}
                    >
                      Clone
                    </Button>
                    <a
                      className="inline-flex min-h-11 items-center justify-center rounded-md border border-border bg-surface px-4 py-2 text-sm hover:bg-border/40"
                      href={`/api/worlds/${w.id}/export`}
                    >
                      Export
                    </a>
                    <Button
                      variant="secondary"
                      disabled={resetMutation.isPending}
                      onClick={() => {
                        const activeNote = w.is_active
                          ? " This is the ACTIVE world — Bedrock will stop, wipe, and regenerate it."
                          : "";
                        if (
                          window.confirm(
                            `Reset "${w.display_name}" to a fresh empty world?` +
                              ` A backup is taken first when level.dat exists.` +
                              ` The world name, folder, and add-on profile are kept.` +
                              activeNote,
                          )
                        ) {
                          resetMutation.mutate(w.id);
                        }
                      }}
                    >
                      Reset
                    </Button>
                    {!w.is_active ? (
                      <Button
                        variant="danger"
                        onClick={() => {
                          if (
                            window.confirm(
                              `Delete world ${w.display_name}? A backup is taken first when possible.`,
                            )
                          ) {
                            deleteMutation.mutate(w.id);
                          }
                        }}
                      >
                        Delete
                      </Button>
                    ) : null}
                  </>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}

      {switchTarget ? (
        <SwitchDialog
          world={switchTarget}
          onClose={() => setSwitchTarget(null)}
          onStarted={(id) => setOperationId(id)}
        />
      ) : null}

      <OperationDrawer
        operationId={operationId}
        onClose={() => setOperationId(null)}
        onFinished={() => refresh()}
      />
    </section>
  );
}
