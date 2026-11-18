import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { EmptyState } from "../../components/ui/EmptyState";
import { Button } from "../../components/ui/Button";
import { SkeletonLines } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/Toast";
import {
  addonLibraryBackupDownloadPath,
  applyWorldAddons,
  createAddonLibraryBackup,
  deleteAddon,
  deleteAddonLibraryBackup,
  downloadAuthenticatedFile,
  fetchAddonLibraryBackups,
  fetchAddons,
  fetchWorldProfile,
  fetchWorlds,
  keepAddonTest,
  restoreAddonLibraryBackup,
  revertAddonTest,
  saveWorldProfile,
  setTexturepackRequired,
  uploadAddon,
} from "../../lib/api";
import type { AddonResponse, WorldAddonEntry } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";
import { OperationDrawer } from "../operations/OperationDrawer";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString([], {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function flagLabel(flag: string): string {
  switch (flag) {
    case "missing_pair":
      return "Depends on a behavior pack that is not in the library";
    case "encrypted":
      return "Encrypted / Marketplace";
    case "needs_beta_apis":
      return "Needs Beta APIs";
    default:
      return flag;
  }
}

export function AddonsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"library" | "world">("library");
  const [worldId, setWorldId] = useState<number | null>(null);
  const [draft, setDraft] = useState<WorldAddonEntry[]>([]);
  const [operationId, setOperationId] = useState<number | null>(null);
  const [pendingWorldId, setPendingWorldId] = useState<number | null>(null);

  const addonsQuery = useQuery({
    queryKey: ["addons"],
    queryFn: fetchAddons,
  });
  const libraryBackupsQuery = useQuery({
    queryKey: ["addon-library-backups"],
    queryFn: fetchAddonLibraryBackups,
    refetchInterval: operationId ? 3000 : 20_000,
  });
  const worldsQuery = useQuery({
    queryKey: ["worlds"],
    queryFn: fetchWorlds,
  });

  const profileQuery = useQuery({
    queryKey: ["addon-profile", worldId],
    queryFn: () => fetchWorldProfile(worldId!),
    enabled: worldId != null,
  });

  const addons = addonsQuery.data?.addons ?? [];
  const libraryBackups = libraryBackupsQuery.data?.backups ?? [];
  const worlds = worldsQuery.data?.worlds ?? [];

  useEffect(() => {
    if (profileQuery.data) {
      setDraft(profileQuery.data.entries);
    }
  }, [profileQuery.data]);

  const uploadMutation = useMutation({
    mutationFn: uploadAddon,
    onSuccess: (data) => {
      setError(null);
      const warns = data.addons.flatMap((a) => a.flags.map(flagLabel));
      if (warns.length) {
        const msg = `Uploaded with flags: ${warns.join("; ")}`;
        setError(msg);
        toast.push(msg, "info");
      } else {
        toast.push("Pack uploaded.", "success");
      }
      void queryClient.invalidateQueries({ queryKey: ["addons"] });
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const backupLibraryMutation = useMutation({
    mutationFn: createAddonLibraryBackup,
    onSuccess: (data) => {
      setError(null);
      setOperationId(data.operation.id);
      toast.push("Add-on library backup started.", "info");
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const restoreLibraryMutation = useMutation({
    mutationFn: restoreAddonLibraryBackup,
    onSuccess: (data) => {
      setError(null);
      setOperationId(data.operation.id);
      toast.push("Add-on library restore started.", "info");
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const deleteLibraryBackupMutation = useMutation({
    mutationFn: deleteAddonLibraryBackup,
    onSuccess: () => {
      setError(null);
      toast.push("Add-on backup deleted.", "success");
      void queryClient.invalidateQueries({ queryKey: ["addon-library-backups"] });
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAddon,
    onSuccess: () => {
      setError(null);
      toast.push("Pack deleted.", "success");
      void queryClient.invalidateQueries({ queryKey: ["addons"] });
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const saveMutation = useMutation({
    mutationFn: () => saveWorldProfile(worldId!, draft),
    onSuccess: (data) => {
      setDraft(data.entries);
      setError(null);
      toast.push("Profile saved.", "success");
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const applyMutation = useMutation({
    mutationFn: (testMode: boolean) => applyWorldAddons(worldId!, testMode),
    onSuccess: (data, testMode) => {
      setError(null);
      setOperationId(data.operation.id);
      toast.push(testMode ? "Test apply started." : "Apply started.", "info");
      if (testMode && worldId != null) setPendingWorldId(worldId);
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const selectedWorld = worlds.find((w) => w.id === worldId) ?? null;

  function toggleInProfile(addon: AddonResponse) {
    setDraft((prev) => {
      const exists = prev.find((e) => e.addon_id === addon.id);
      if (exists) {
        return prev.filter((e) => e.addon_id !== addon.id);
      }
      return [
        ...prev,
        {
          addon_id: addon.id,
          enabled: true,
          load_order: prev.length,
          addon,
        },
      ];
    });
  }

  function selectAllPacks() {
    setDraft(
      addons.map((addon, index) => ({
        addon_id: addon.id,
        enabled: true,
        load_order: index,
        addon,
      })),
    );
  }

  function deselectAllPacks() {
    setDraft([]);
  }

  const enabledCount = draft.filter((e) => e.enabled).length;
  const allSelected = addons.length > 0 && enabledCount === addons.length;
  const noneSelected = enabledCount === 0;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = !allSelected && !noneSelected;
    }
  }, [allSelected, noneSelected]);

  function loadProfile(id: number) {
    setWorldId(id);
    setDraft([]);
    void fetchWorldProfile(id)
      .then((data) => setDraft(data.entries))
      .catch((err: Error) => setError(err.message));
  }

  return (
    <section className="space-y-6">
      <div className="space-y-2 page-enter">
        <h1 className="font-pixel text-2xl text-primary mf-title-glow">Add-ons</h1>
        <p className="max-w-xl text-muted leading-relaxed">
          Upload packs, assign them per world, then Apply or Test (auto-reverts if you
          do not keep the change). Admins can also backup and restore the whole library.
        </p>
      </div>

      <div className="flex gap-2">
        <Button
          variant={tab === "library" ? "primary" : "secondary"}
          onClick={() => setTab("library")}
        >
          Library
        </Button>
        <Button
          variant={tab === "world" ? "primary" : "secondary"}
          onClick={() => setTab("world")}
        >
          Per world
        </Button>
      </div>

      {error ? (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}

      {tab === "library" ? (
        <div className="space-y-4">
          {isAdmin ? (
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => fileRef.current?.click()}
                disabled={uploadMutation.isPending}
              >
                Upload .mcaddon / .mcpack
              </Button>
              <input
                ref={fileRef}
                type="file"
                accept=".mcaddon,.mcpack,.zip"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) uploadMutation.mutate(file);
                  e.target.value = "";
                }}
              />
              <Button
                variant="secondary"
                onClick={() => backupLibraryMutation.mutate()}
                disabled={backupLibraryMutation.isPending}
              >
                Backup library
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  void setTexturepackRequired(true)
                    .then(() => setError(null))
                    .catch((err: Error) => setError(err.message))
                }
              >
                Require texture pack
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  void setTexturepackRequired(false)
                    .then(() => setError(null))
                    .catch((err: Error) => setError(err.message))
                }
              >
                Optional texture pack
              </Button>
            </div>
          ) : null}

          {addonsQuery.isLoading ? (
            <SkeletonLines count={4} />
          ) : addons.length === 0 ? (
            <EmptyState
              title="Library is empty"
              description="Upload a .mcaddon or .mcpack to build your pack library, then assign packs per world."
              action={
                isAdmin ? (
                  <Button
                    onClick={() => fileRef.current?.click()}
                    disabled={uploadMutation.isPending}
                  >
                    Upload pack
                  </Button>
                ) : null
              }
            />
          ) : (
            <div className="space-y-2">
              <div className="max-h-[min(60vh,36rem)] overflow-y-auto rounded-md border border-border">
                <ul className="divide-y divide-border">
                  {addons.map((a) => (
                    <li
                      key={a.id}
                      className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 space-y-1">
                        <p className="font-medium truncate">
                          {a.name}{" "}
                          <span className="text-muted font-normal text-sm">
                            {a.kind} · v{a.version}
                          </span>
                        </p>
                        <p className="text-xs text-muted">
                          {formatBytes(a.size_bytes)}
                          {a.pair_name ? ` · paired with ${a.pair_name}` : ""}
                        </p>
                        {a.flags.length ? (
                          <p className="text-xs text-warning">
                            {a.flags.map(flagLabel).join(" · ")}
                          </p>
                        ) : null}
                      </div>
                      {isAdmin ? (
                        <Button
                          variant="danger"
                          onClick={() => {
                            if (window.confirm(`Delete ${a.name}?`)) {
                              deleteMutation.mutate(a.id);
                            }
                          }}
                        >
                          Delete
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
              <p className="text-xs text-muted">
                {addons.length} pack{addons.length === 1 ? "" : "s"} in library
              </p>
            </div>
          )}

          <div className="space-y-3 pt-2">
            <h2 className="font-pixel text-lg text-text">Library backups</h2>
            <p className="text-sm text-muted">
              Saves every pack plus per-world assignments. Restore replaces the current
              library (a safety backup is taken first).
            </p>
            {libraryBackupsQuery.isLoading ? (
              <SkeletonLines count={3} />
            ) : libraryBackups.length === 0 ? (
              <p className="text-sm text-muted">No library backups yet.</p>
            ) : (
              <div className="max-h-72 overflow-y-auto rounded-md border border-border">
                <ul className="divide-y divide-border">
                  {libraryBackups.map((b) => (
                    <li
                      key={b.id}
                      className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between mf-card"
                    >
                      <div className="min-w-0 space-y-1">
                        <p className="font-medium truncate">
                          Backup #{b.id}
                          {b.note ? (
                            <span className="text-muted font-normal"> · {b.note}</span>
                          ) : null}
                        </p>
                        <p className="text-xs text-muted">
                          {b.pack_count} packs · {formatBytes(b.size_bytes)}
                          {b.verified ? " · verified" : ""} · {formatWhen(b.created_at)}
                        </p>
                      </div>
                      {isAdmin ? (
                        <div className="flex flex-wrap gap-2">
                          <Button
                            variant="secondary"
                            onClick={() => {
                              if (
                                window.confirm(
                                  `Restore add-on library from backup #${b.id}? Current packs will be replaced after a safety backup.`,
                                )
                              ) {
                                restoreLibraryMutation.mutate(b.id);
                              }
                            }}
                            disabled={restoreLibraryMutation.isPending}
                          >
                            Restore
                          </Button>
                          <Button
                            variant="secondary"
                            className="mf-pressable"
                            onClick={() => {
                              void downloadAuthenticatedFile(
                                addonLibraryBackupDownloadPath(b.id),
                                `addon-library-backup-${b.id}.tar.zst`,
                              ).catch((err: unknown) => {
                                const message =
                                  err instanceof Error
                                    ? err.message
                                    : "Download failed";
                                toast.push(message, "error");
                              });
                            }}
                          >
                            Save to device
                          </Button>
                          <Button
                            variant="danger"
                            onClick={() => {
                              if (window.confirm(`Delete add-on backup #${b.id}?`)) {
                                deleteLibraryBackupMutation.mutate(b.id);
                              }
                            }}
                            disabled={deleteLibraryBackupMutation.isPending}
                          >
                            Delete
                          </Button>
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <label className="block space-y-1 text-sm max-w-sm">
            <span className="text-muted">World</span>
            <select
              className="min-h-11 w-full rounded-md border border-border bg-surface px-3"
              value={worldId ?? ""}
              onChange={(e) => {
                const id = Number(e.target.value);
                if (id) loadProfile(id);
              }}
            >
              <option value="">Select a world…</option>
              {worlds.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.display_name}
                  {w.is_active ? " (active)" : ""}
                </option>
              ))}
            </select>
          </label>

          {selectedWorld && isAdmin ? (
            <>
              <p className="text-sm text-muted">
                Download size:{" "}
                {formatBytes(profileQuery.data?.download_size.enabled_pack_bytes ?? 0)}{" "}
                ({profileQuery.data?.download_size.enabled_pack_count ?? enabledCount}{" "}
                packs)
              </p>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-muted">
                  Selected {enabledCount}/{addons.length}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={selectAllPacks}
                    disabled={allSelected || addons.length === 0}
                  >
                    Select all
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={deselectAllPacks}
                    disabled={noneSelected}
                  >
                    Deselect all
                  </Button>
                </div>
              </div>
              <div className="max-h-[min(50vh,28rem)] overflow-y-auto rounded-md border border-border p-3">
                <div className="mb-3 flex items-center gap-3 border-b border-border pb-2 text-sm">
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    id="addon-select-all"
                    checked={allSelected}
                    onChange={() => {
                      if (allSelected) deselectAllPacks();
                      else selectAllPacks();
                    }}
                    disabled={addons.length === 0}
                  />
                  <label htmlFor="addon-select-all" className="font-medium text-text">
                    {allSelected ? "Deselect all packs" : "Select all packs"}
                  </label>
                </div>
                <ul className="space-y-2">
                  {addons.map((a) => {
                    const on = draft.some((e) => e.addon_id === a.id && e.enabled);
                    return (
                      <li key={a.id} className="flex items-center gap-3 text-sm">
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={() => toggleInProfile(a)}
                          id={`addon-${a.id}`}
                        />
                        <label htmlFor={`addon-${a.id}`}>
                          {a.name}{" "}
                          <span className="text-muted">
                            ({a.kind}
                            {a.encrypted ? ", encrypted" : ""}
                            {a.missing_pair ? ", missing pair" : ""})
                          </span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending}
                >
                  Save profile
                </Button>
                <Button
                  onClick={() => applyMutation.mutate(false)}
                  disabled={applyMutation.isPending}
                >
                  Apply
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => applyMutation.mutate(true)}
                  disabled={applyMutation.isPending}
                >
                  Test
                </Button>
                {pendingWorldId === worldId ? (
                  <>
                    <Button
                      onClick={() =>
                        void keepAddonTest(worldId!)
                          .then(() => {
                            setPendingWorldId(null);
                            setError(null);
                          })
                          .catch((err: Error) => setError(err.message))
                      }
                    >
                      Keep test
                    </Button>
                    <Button
                      variant="danger"
                      onClick={() =>
                        void revertAddonTest(worldId!)
                          .then(() => {
                            setPendingWorldId(null);
                            setError(null);
                          })
                          .catch((err: Error) => setError(err.message))
                      }
                    >
                      Revert now
                    </Button>
                  </>
                ) : null}
              </div>
            </>
          ) : selectedWorld ? (
            <p className="text-muted text-sm">Only admins can edit world profiles.</p>
          ) : null}
        </div>
      )}

      <OperationDrawer
        operationId={operationId}
        onClose={() => setOperationId(null)}
        onFinished={() => {
          void queryClient.invalidateQueries({ queryKey: ["addons"] });
          void queryClient.invalidateQueries({
            queryKey: ["addon-library-backups"],
          });
          if (worldId != null) {
            void queryClient.invalidateQueries({
              queryKey: ["addon-profile", worldId],
            });
          }
        }}
      />
    </section>
  );
}
