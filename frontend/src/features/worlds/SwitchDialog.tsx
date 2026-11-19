import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Icon, Icons } from "../../components/icons";
import { Button } from "../../components/ui/Button";
import { createSwitchRequest, fetchSwitchStatus, switchWorld } from "../../lib/api";
import type { WorldResponse } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";

type Props = {
  world: WorldResponse;
  onClose: () => void;
  onStarted: (operationId: number) => void;
};

type Phase = "review" | "consent" | "confirm";

const PREVIEW_STEPS = [
  { id: "warn", label: "Warn players in-game", icon: Icons.Users },
  { id: "backup", label: "Backup the current world", icon: Icons.Backups },
  { id: "stop", label: "Stop Bedrock safely", icon: Icons.Offline },
  { id: "swap", label: "Load the new world & packs", icon: Icons.Worlds },
  { id: "start", label: "Start and wait for healthy", icon: Icons.Status },
] as const;

export function SwitchDialog({ world, onClose, onStarted }: Props) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [error, setError] = useState<string | null>(null);
  const [consentId, setConsentId] = useState<string | null>(null);
  const [skipCountdown, setSkipCountdown] = useState(false);
  const [phase, setPhase] = useState<Phase>("review");

  const statusQuery = useQuery({
    queryKey: ["switch-status"],
    queryFn: fetchSwitchStatus,
    refetchInterval: 3000,
  });

  const status = statusQuery.data;
  const online = status?.players_online ?? 0;
  const openReq = status?.open_consent_requests.find(
    (r) => r.target_world_id === world.id,
  );
  const activeConsent = consentId
    ? (status?.open_consent_requests.find((r) => r.id === consentId) ?? openReq)
    : openReq;

  const requestMutation = useMutation({
    mutationFn: () => createSwitchRequest(world.id),
    onSuccess: (data) => {
      setConsentId(data.id);
      setError(null);
      setPhase("consent");
      void statusQuery.refetch();
    },
    onError: (err: Error) => setError(err.message),
  });

  const switchMutation = useMutation({
    mutationFn: (opts: { force?: boolean; consent_id?: string }) =>
      switchWorld(world.id, {
        force: opts.force,
        skip_countdown: isAdmin && skipCountdown,
        consent_id: opts.consent_id,
      }),
    onSuccess: (data) => {
      setError(null);
      onStarted(data.operation.id);
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  const canSwitchQuiet = online === 0;
  const consentReady = Boolean(activeConsent?.satisfied);

  const phaseIndex = useMemo(() => {
    if (phase === "review") return 0;
    if (phase === "consent") return 1;
    return 2;
  }, [phase]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-label="Switch world"
    >
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label="Dismiss switch dialog"
        onClick={onClose}
      />
      <div className="mf-sheet mf-sheet-above-nav relative z-10 flex w-full max-w-md flex-col rounded-t-2xl border border-border bg-surface shadow-xl sm:rounded-xl animate-slide-up sm:mb-0 sm:max-h-[min(92vh,40rem)]">
        <div className="shrink-0 border-b border-border bg-surface px-5 pt-3 pb-4">
          <div
            className="mx-auto mb-3 h-1 w-10 rounded-full bg-border sm:hidden"
            aria-hidden
          />
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <h2 className="font-pixel text-lg text-text">Switch world</h2>
              <p className="text-sm text-muted truncate">
                To <span className="text-text">{world.display_name}</span>
              </p>
            </div>
            <Button variant="ghost" onClick={onClose} aria-label="Cancel switch">
              <Icon icon={Icons.Close} size={16} />
            </Button>
          </div>

          <ol className="mt-4 flex items-center gap-2" aria-label="Switch steps">
            {(["Review", "Players", "Confirm"] as const).map((label, index) => {
              const active = index === phaseIndex;
              const done = index < phaseIndex;
              return (
                <li key={label} className="flex flex-1 items-center gap-2 min-w-0">
                  <span
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs ${
                      done
                        ? "border-primary/40 bg-primary/15 text-primary"
                        : active
                          ? "border-accent/50 bg-accent/15 text-accent"
                          : "border-border text-muted"
                    }`}
                  >
                    {done ? <Icon icon={Icons.Check} size={14} /> : index + 1}
                  </span>
                  <span
                    className={`text-[11px] truncate sm:text-xs ${
                      active ? "text-text" : "text-muted"
                    }`}
                  >
                    {label}
                  </span>
                  {index < 2 ? (
                    <span className="ml-auto hidden h-px flex-1 bg-border sm:block" />
                  ) : null}
                </li>
              );
            })}
          </ol>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4 space-y-4">
          {phase === "review" ? (
            <>
              <p className="text-sm text-muted leading-relaxed">
                MineForge will walk through these steps. Progress stays visible on
                screen — including on mobile — until the new world is healthy.
              </p>
              <ol className="space-y-3">
                {PREVIEW_STEPS.map((step, index) => (
                  <li
                    key={step.id}
                    className="flex items-start gap-3 animate-slide-up"
                    style={{ animationDelay: `${index * 45}ms` }}
                  >
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-border/20 text-primary">
                      <Icon icon={step.icon} size={16} />
                    </span>
                    <div>
                      <p className="text-sm text-text">{step.label}</p>
                      {step.id === "warn" ? (
                        <p className="text-xs text-muted">
                          Countdown {status?.countdown_seconds ?? 30}s
                          {(status?.cooldown_remaining_seconds ?? 0) > 0
                            ? ` · cooldown ${status?.cooldown_remaining_seconds}s`
                            : ""}
                        </p>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>
            </>
          ) : null}

          {phase === "consent" ? (
            <div className="space-y-3">
              <p className="text-sm text-muted leading-relaxed">
                {online > 0
                  ? "Players are online. Request approvals or wait until the world is empty."
                  : "No players online — you can continue."}
              </p>
              <div className="mf-card p-3 space-y-2">
                <p className="inline-flex items-center gap-2 text-sm text-text">
                  <Icon icon={Icons.Players} size={16} />
                  {online} online
                </p>
                {online > 0 ? (
                  <p className="text-xs text-warning">
                    {status?.online_gamertags.join(", ") || "unknown"}
                  </p>
                ) : null}
                {activeConsent ? (
                  <p className="text-sm text-muted">
                    Consent {activeConsent.approval_count}/
                    {activeConsent.required_count}
                    {activeConsent.satisfied ? " — ready" : " — waiting"}
                  </p>
                ) : null}
              </div>
              {online > 0 && !consentReady ? (
                <Button
                  variant="secondary"
                  className="w-full justify-center gap-2"
                  onClick={() => requestMutation.mutate()}
                  disabled={requestMutation.isPending}
                >
                  <Icon icon={Icons.Shield} size={16} />
                  {requestMutation.isPending ? "Requesting…" : "Request approvals"}
                </Button>
              ) : null}
            </div>
          ) : null}

          {phase === "confirm" ? (
            <div className="space-y-3">
              <p className="text-sm text-muted leading-relaxed">
                Ready to switch to{" "}
                <span className="text-text">{world.display_name}</span> (
                {world.folder_name}). A live progress panel will track each step.
              </p>
              {isAdmin ? (
                <label className="flex items-center gap-2 text-sm text-muted">
                  <input
                    type="checkbox"
                    checked={skipCountdown}
                    onChange={(e) => setSkipCountdown(e.target.checked)}
                  />
                  Skip countdown
                </label>
              ) : null}
            </div>
          ) : null}

          {error ? (
            <p className="text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </div>

        <div className="shrink-0 flex flex-wrap gap-2 justify-between border-t border-border bg-surface px-5 py-3">
          <Button
            variant="ghost"
            onClick={() => {
              if (phase === "review") onClose();
              else if (phase === "consent") setPhase("review");
              else setPhase(online > 0 ? "consent" : "review");
            }}
          >
            {phase === "review" ? "Cancel" : "Back"}
          </Button>

          <div className="flex flex-wrap gap-2 justify-end">
            {phase === "review" ? (
              <Button
                onClick={() => setPhase(online > 0 ? "consent" : "confirm")}
                className="gap-2"
              >
                Continue
                <Icon icon={Icons.Chevron} size={16} />
              </Button>
            ) : null}

            {phase === "consent" ? (
              <Button
                onClick={() => setPhase("confirm")}
                disabled={!canSwitchQuiet && !consentReady}
                className="gap-2"
              >
                Continue
                <Icon icon={Icons.Chevron} size={16} />
              </Button>
            ) : null}

            {phase === "confirm" ? (
              <>
                <Button
                  onClick={() =>
                    switchMutation.mutate({
                      consent_id: activeConsent?.satisfied
                        ? activeConsent.id
                        : undefined,
                    })
                  }
                  disabled={
                    switchMutation.isPending || (!canSwitchQuiet && !consentReady)
                  }
                  className="gap-2"
                >
                  <Icon icon={Icons.Worlds} size={16} />
                  {switchMutation.isPending ? "Starting…" : "Start switch"}
                </Button>
                {isAdmin && online > 0 ? (
                  <Button
                    variant="danger"
                    onClick={() => {
                      if (
                        window.confirm(
                          `Force switch while online: ${status?.online_gamertags.join(", ") || online + " players"}?`,
                        )
                      ) {
                        switchMutation.mutate({ force: true });
                      }
                    }}
                    disabled={switchMutation.isPending}
                  >
                    Force
                  </Button>
                ) : null}
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
