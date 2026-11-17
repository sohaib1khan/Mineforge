import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "../../components/ui/Button";
import { createSwitchRequest, fetchSwitchStatus, switchWorld } from "../../lib/api";
import type { WorldResponse } from "../../lib/types";
import { useAuth } from "../auth/AuthContext";

type Props = {
  world: WorldResponse;
  onClose: () => void;
  onStarted: (operationId: number) => void;
};

export function SwitchDialog({ world, onClose, onStarted }: Props) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [error, setError] = useState<string | null>(null);
  const [consentId, setConsentId] = useState<string | null>(null);
  const [skipCountdown, setSkipCountdown] = useState(false);

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

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label="Switch world"
    >
      <div className="w-full max-w-md rounded-lg border border-border bg-surface p-5 shadow-xl space-y-4">
        <div className="space-y-1">
          <h2 className="font-pixel text-lg text-text">Switch world</h2>
          <p className="text-sm text-muted">
            Switch to <span className="text-text">{world.display_name}</span> (
            {world.folder_name}). A pre-switch backup is taken first.
          </p>
        </div>

        <ul className="text-sm text-muted space-y-1">
          <li>Players online: {online}</li>
          {online > 0 ? (
            <li className="text-warning">
              {status?.online_gamertags.join(", ") || "unknown"}
            </li>
          ) : null}
          {(status?.cooldown_remaining_seconds ?? 0) > 0 ? (
            <li>
              Cooldown: {status?.cooldown_remaining_seconds}s
              {isAdmin ? " (admins may still switch)" : ""}
            </li>
          ) : null}
          <li>Countdown: {status?.countdown_seconds ?? 30}s in-game warning</li>
        </ul>

        {activeConsent ? (
          <p className="text-sm text-muted">
            Consent {activeConsent.approval_count}/{activeConsent.required_count}
            {activeConsent.satisfied ? " — ready" : " — waiting for approvals"}
          </p>
        ) : null}

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

        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}

        <div className="flex flex-wrap gap-2 justify-end">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          {online > 0 && !consentReady ? (
            <Button
              variant="secondary"
              onClick={() => requestMutation.mutate()}
              disabled={requestMutation.isPending}
            >
              Request approvals
            </Button>
          ) : null}
          <Button
            onClick={() =>
              switchMutation.mutate({
                consent_id: activeConsent?.satisfied ? activeConsent.id : undefined,
              })
            }
            disabled={switchMutation.isPending || (!canSwitchQuiet && !consentReady)}
          >
            Switch
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
              Force switch
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
