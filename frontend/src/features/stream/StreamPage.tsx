import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Button } from "../../components/ui/Button";
import { SkeletonLines } from "../../components/ui/Skeleton";
import { useToast } from "../../components/ui/Toast";
import {
  fetchStreamSettings,
  fetchStreamStatus,
  rotateStreamKey,
  updateStreamSettings,
} from "../../lib/api";
import { copyText } from "../../lib/clipboard";
import { useAuth } from "../auth/AuthContext";
import { StreamPlayer } from "./StreamPlayer";

async function copyOrToast(
  value: string,
  okMessage: string,
  push: (message: string, tone: "success" | "error" | "info") => void,
): Promise<void> {
  const ok = await copyText(value);
  push(
    ok ? okMessage : "Copy failed — select the text and copy manually.",
    ok ? "success" : "error",
  );
}

function formatDuration(startedAt: string | null): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  if (Number.isNaN(start)) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - start) / 1000));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
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

export function StreamPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const [adminOpen, setAdminOpen] = useState(false);
  const [obsOpen, setObsOpen] = useState(false);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [revealedObsKey, setRevealedObsKey] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState<string | null>(null);
  const [descriptionDraft, setDescriptionDraft] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["stream-status"],
    queryFn: fetchStreamStatus,
    refetchInterval: 10_000,
  });

  const settingsQuery = useQuery({
    queryKey: ["stream-settings"],
    queryFn: fetchStreamSettings,
    enabled: isAdmin,
  });

  const saveMutation = useMutation({
    mutationFn: updateStreamSettings,
    onSuccess: () => {
      toast.push("Stream settings saved.", "success");
      setTitleDraft(null);
      setDescriptionDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["stream-settings"] });
      void queryClient.invalidateQueries({ queryKey: ["stream-status"] });
    },
    onError: (err: Error) => toast.push(err.message, "error"),
  });

  const rotateMutation = useMutation({
    mutationFn: rotateStreamKey,
    onSuccess: (data) => {
      setRevealedKey(data.stream_key);
      setRevealedObsKey(data.obs_stream_key);
      setObsOpen(true);
      setAdminOpen(true);
      toast.push(data.warning, "info");
      void queryClient.invalidateQueries({ queryKey: ["stream-settings"] });
    },
    onError: (err: Error) => toast.push(err.message, "error"),
  });

  const status = statusQuery.data;
  const settings = settingsQuery.data;
  const title = titleDraft ?? settings?.title ?? status?.title ?? "MineForge Live";
  const description =
    descriptionDraft ?? settings?.description ?? status?.description ?? "";

  const liveBadge = useMemo(() => {
    if (!status) return null;
    if (status.live) {
      return (
        <span className="inline-flex items-center gap-2 rounded-md bg-danger/15 px-2 py-1 text-xs font-medium text-danger">
          <span className="mf-status-pulse h-2 w-2 rounded-full bg-danger" />
          LIVE
        </span>
      );
    }
    return (
      <span className="inline-flex items-center rounded-md bg-border/40 px-2 py-1 text-xs font-medium text-muted">
        OFFLINE
      </span>
    );
  }, [status]);

  return (
    <section className="space-y-6">
      <div className="space-y-2 page-enter">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-pixel text-2xl text-primary mf-title-glow">
            {status?.title ?? "Stream"}
          </h1>
          {liveBadge}
        </div>
        <p className="max-w-2xl text-muted leading-relaxed">
          {status?.description ||
            "Watch the game live when the admin is streaming from OBS."}
        </p>
        {status?.live ? (
          <p className="text-sm text-muted">
            Live for {formatDuration(status.started_at)} · {status.viewers} viewer
            {status.viewers === 1 ? "" : "s"}
            {status.video_codec ? ` · ${status.video_codec}` : ""}
          </p>
        ) : (
          <p className="text-sm text-muted">
            Last stream: {formatWhen(status?.last_ended_at ?? null)}
          </p>
        )}
      </div>

      {statusQuery.isLoading ? (
        <SkeletonLines count={6} />
      ) : (
        <StreamPlayer live={Boolean(status?.live && status.enabled)} />
      )}

      {isAdmin ? (
        <div className="mf-card space-y-4 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-pixel text-lg text-primary">Admin</h2>
            <Button variant="ghost" onClick={() => setAdminOpen((open) => !open)}>
              {adminOpen ? "Hide" : "Show"} panel
            </Button>
          </div>
          {adminOpen ? (
            <div className="space-y-4">
              {settingsQuery.isLoading ? (
                <SkeletonLines count={4} />
              ) : (
                <>
                  <label className="block space-y-1 text-sm">
                    <span className="text-muted">Title</span>
                    <input
                      className="w-full rounded-md border border-border bg-bg px-3 py-2"
                      value={title}
                      onChange={(e) => setTitleDraft(e.target.value)}
                    />
                  </label>
                  <label className="block space-y-1 text-sm">
                    <span className="text-muted">Description</span>
                    <textarea
                      className="min-h-20 w-full rounded-md border border-border bg-bg px-3 py-2"
                      value={description}
                      onChange={(e) => setDescriptionDraft(e.target.value)}
                    />
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={settings?.enabled ?? true}
                      onChange={(e) =>
                        saveMutation.mutate({ enabled: e.target.checked })
                      }
                    />
                    Stream page enabled (accept OBS publish)
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      onClick={() =>
                        saveMutation.mutate({
                          title,
                          description,
                          enabled: settings?.enabled,
                        })
                      }
                      disabled={saveMutation.isPending}
                    >
                      Save
                    </Button>
                    <Button variant="secondary" onClick={() => setObsOpen((o) => !o)}>
                      {obsOpen ? "Hide OBS setup" : "Show OBS setup"}
                    </Button>
                  </div>
                  {obsOpen && settings ? (
                    <div className="space-y-3 rounded-md border border-border bg-bg/60 p-3 text-sm">
                      <p className="font-medium text-text">
                        OBS → Settings → Stream → Service:{" "}
                        <span className="text-primary">Custom</span> (not Twitch)
                      </p>
                      <div className="space-y-1">
                        <p className="text-muted">Server (paste into OBS Server)</p>
                        <div className="flex flex-wrap items-start gap-2">
                          <code className="min-w-0 flex-1 break-all rounded bg-border/40 px-2 py-1">
                            {settings.rtmp_server}
                          </code>
                          <Button
                            variant="secondary"
                            onClick={() => {
                              void copyOrToast(
                                settings.rtmp_server,
                                "Copied OBS server URL.",
                                toast.push,
                              );
                            }}
                          >
                            Copy
                          </Button>
                        </div>
                        <p className="text-xs text-muted">
                          Must start with rtmp:// — not https://
                          {settings.rtmp_host
                            ? ` (host: ${settings.rtmp_host}:${settings.rtmp_port})`
                            : ""}
                        </p>
                        <p className="text-xs text-danger">
                          If this hostname is behind Cloudflare (orange cloud), OBS will
                          fail to connect. Use a DNS-only hostname or the server&apos;s
                          public IP for RTMP, and open TCP {settings.rtmp_port}.
                        </p>
                      </div>
                      <div className="space-y-1">
                        <p className="text-muted">
                          Stream Key (paste into OBS Stream Key — includes
                          ?user=…&amp;pass=…)
                        </p>
                        {revealedObsKey ? (
                          <div className="flex flex-wrap items-start gap-2">
                            <code className="min-w-0 flex-1 break-all rounded bg-border/40 px-2 py-1">
                              {revealedObsKey}
                            </code>
                            <Button
                              variant="secondary"
                              onClick={() => {
                                void copyOrToast(
                                  revealedObsKey,
                                  "Copied OBS stream key field.",
                                  toast.push,
                                );
                              }}
                            >
                              Copy
                            </Button>
                          </div>
                        ) : (
                          <p className="text-sm">{settings.rtmp_stream_key_hint}</p>
                        )}
                        {revealedKey ? (
                          <p className="text-xs text-muted break-all">
                            Raw key (advanced): {revealedKey}
                          </p>
                        ) : null}
                      </div>
                      <Button
                        variant="danger"
                        disabled={rotateMutation.isPending}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Rotate the stream key? The current OBS key will stop working immediately.",
                            )
                          ) {
                            rotateMutation.mutate();
                          }
                        }}
                      >
                        Regenerate key
                      </Button>
                      <ul className="list-disc space-y-1 pl-5 text-muted">
                        {settings.obs_notes.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                      <p className="text-xs text-muted">
                        Reminder: the stream shows gamertags, chat, and coordinates —
                        capture the game window only. Forward TCP {settings.rtmp_port}{" "}
                        if streaming from outside your home network.
                      </p>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
