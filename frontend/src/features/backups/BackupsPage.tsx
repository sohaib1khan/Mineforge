import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { EmptyState } from "../../components/ui/EmptyState";
import { Button } from "../../components/ui/Button";
import { SkeletonLines } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/Toast";
import {
  backupDownloadPath,
  createBackup,
  deleteBackup,
  downloadAuthenticatedFile,
  fetchBackups,
  restoreBackup,
} from "../../lib/api";
import { useAuth } from "../auth/AuthContext";
import { OperationDrawer } from "../operations/OperationDrawer";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function BackupsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const [operationId, setOperationId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["backups"],
    queryFn: () => fetchBackups(),
    refetchInterval: operationId ? 3000 : 15_000,
  });

  const onFinished = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["backups"] });
  }, [queryClient]);

  const backupMutation = useMutation({
    mutationFn: createBackup,
    onSuccess: (data) => {
      setError(null);
      setOperationId(data.operation.id);
      toast.push("Backup started.", "info");
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const restoreMutation = useMutation({
    mutationFn: restoreBackup,
    onSuccess: (data) => {
      setError(null);
      setOperationId(data.operation.id);
      toast.push("Restore started.", "info");
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteBackup,
    onSuccess: () => {
      setError(null);
      toast.push("Backup deleted.", "success");
      void queryClient.invalidateQueries({ queryKey: ["backups"] });
    },
    onError: (err: Error) => {
      setError(err.message);
      toast.push(err.message, "error");
    },
  });

  const backups = listQuery.data?.backups ?? [];
  const storage = listQuery.data?.storage;

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <h1 className="font-pixel text-2xl text-text">Backups</h1>
          <p className="max-w-xl text-muted leading-relaxed">
            Verified world archives. Live backups use save hold while players are
            online.
          </p>
        </div>
        <Button
          onClick={() => backupMutation.mutate()}
          disabled={backupMutation.isPending}
        >
          {backupMutation.isPending ? "Starting…" : "Backup now"}
        </Button>
      </div>

      {storage ? (
        <p className="text-sm text-muted">
          Storage: {formatBytes(storage.backups_bytes ?? 0)} across{" "}
          {storage.backup_file_count ?? 0} file
          {(storage.backup_file_count ?? 0) === 1 ? "" : "s"}
        </p>
      ) : null}

      {error ? (
        <p className="text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}

      {listQuery.isLoading ? (
        <SkeletonLines count={4} />
      ) : backups.length === 0 ? (
        <EmptyState
          title="No backups yet"
          description="Create a backup while a world exists. Live backups work with players online."
          action={
            <Button
              onClick={() => backupMutation.mutate()}
              disabled={backupMutation.isPending}
            >
              Backup now
            </Button>
          }
        />
      ) : (
        <div className="max-h-[min(65vh,40rem)] overflow-y-auto rounded-md border border-border">
          <ul className="divide-y divide-border">
            {backups.map((b) => (
              <li
                key={b.id}
                className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 space-y-1">
                  <p className="font-medium text-text truncate">
                    {b.world_folder}{" "}
                    <span className="text-muted font-normal">#{b.id}</span>
                  </p>
                  <p className="text-xs text-muted">
                    {b.kind} · {formatBytes(b.size_bytes)} ·{" "}
                    {b.verified ? "verified" : "unverified"} ·{" "}
                    {formatWhen(b.created_at)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {isAdmin ? (
                    <>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          if (
                            window.confirm(
                              `Restore backup #${b.id} for ${b.world_folder}? A pre-restore backup is taken first.`,
                            )
                          ) {
                            restoreMutation.mutate(b.id);
                          }
                        }}
                        disabled={restoreMutation.isPending}
                      >
                        Restore
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => {
                          void downloadAuthenticatedFile(
                            backupDownloadPath(b.id),
                            `${b.world_folder}-backup-${b.id}.tar.zst`,
                          ).catch((err: unknown) => {
                            const message =
                              err instanceof Error ? err.message : "Download failed";
                            toast.push(message, "error");
                          });
                        }}
                      >
                        Save to device
                      </Button>
                      <Button
                        variant="danger"
                        onClick={() => {
                          if (window.confirm(`Delete backup #${b.id}?`)) {
                            deleteMutation.mutate(b.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        Delete
                      </Button>
                    </>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <OperationDrawer
        operationId={operationId}
        onClose={() => setOperationId(null)}
        onFinished={onFinished}
      />
    </section>
  );
}
