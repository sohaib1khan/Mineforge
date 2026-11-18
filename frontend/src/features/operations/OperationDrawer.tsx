import { useEffect, useRef, useState } from "react";

import { Button } from "../../components/ui/Button";
import { Icon, Icons } from "../../components/icons";
import { fetchOperation } from "../../lib/api";
import type { OperationResponse } from "../../lib/types";
import {
  deriveOperationSteps,
  operationTitle,
  type OperationStep,
  type StepState,
} from "./operationSteps";

type Props = {
  operationId: number | null;
  onClose: () => void;
  onFinished?: (op: OperationResponse) => void;
};

const terminal = new Set(["succeeded", "failed", "rolled_back"]);

function stepIcon(state: StepState) {
  if (state === "done") return Icons.Check;
  if (state === "failed") return Icons.Close;
  if (state === "active") return Icons.Timer;
  return Icons.Chevron;
}

function StepRow({ step, index }: { step: OperationStep; index: number }) {
  const Lucide = stepIcon(step.state);
  const tone =
    step.state === "done"
      ? "text-primary border-primary/40 bg-primary/10"
      : step.state === "active"
        ? "text-accent border-accent/50 bg-accent/10 mf-status-pulse"
        : step.state === "failed"
          ? "text-danger border-danger/40 bg-danger/10"
          : "text-muted border-border bg-surface";

  return (
    <li
      className="flex items-start gap-3 animate-slide-up"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <span
        className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${tone}`}
        aria-hidden
      >
        <Icon icon={Lucide} size={14} />
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <p
          className={`text-sm ${step.state === "pending" ? "text-muted" : "text-text"}`}
        >
          {step.label}
        </p>
        {step.detail ? <p className="text-xs text-muted">{step.detail}</p> : null}
      </div>
    </li>
  );
}

export function OperationDrawer({ operationId, onClose, onFinished }: Props) {
  const [op, setOp] = useState<OperationResponse | null>(null);
  const [expanded, setExpanded] = useState(false);
  const logRef = useRef<HTMLPreElement>(null);
  const finishedRef = useRef(false);

  useEffect(() => {
    finishedRef.current = false;
    setExpanded(false);
    if (operationId == null) {
      setOp(null);
      return;
    }

    let cancelled = false;
    let source: EventSource | null = null;

    const poll = async () => {
      try {
        const latest = await fetchOperation(operationId);
        if (!cancelled) {
          setOp(latest);
          if (terminal.has(latest.status) && !finishedRef.current) {
            finishedRef.current = true;
            onFinished?.(latest);
          }
        }
      } catch {
        // keep last known
      }
    };

    void poll();
    const interval = window.setInterval(() => void poll(), 1500);

    try {
      source = new EventSource(`/api/operations/${operationId}/stream`, {
        withCredentials: true,
      });
      source.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as OperationResponse;
          if (!cancelled) {
            setOp(payload);
            if (terminal.has(payload.status) && !finishedRef.current) {
              finishedRef.current = true;
              onFinished?.(payload);
            }
          }
        } catch {
          // ignore malformed
        }
      };
    } catch {
      // EventSource unavailable — polling still works
    }

    return () => {
      cancelled = true;
      window.clearInterval(interval);
      source?.close();
    };
  }, [operationId, onFinished]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [op?.log]);

  if (operationId == null) {
    return null;
  }

  const status = op?.status ?? "queued";
  const done = terminal.has(status);
  const steps = deriveOperationSteps(op?.type, op?.log ?? "", status);
  const activeStep = [...steps].reverse().find((s) => s.state === "active");
  const progress =
    steps.length === 0
      ? 0
      : Math.round(
          (steps.filter((s) => s.state === "done").length / steps.length) * 100,
        );

  const statusLabel =
    status === "rolled_back"
      ? "Rolled back"
      : status === "succeeded"
        ? "Succeeded"
        : status === "failed"
          ? "Failed"
          : status === "running"
            ? "Running"
            : "Queued";

  return (
    <div
      className="mf-op-drawer fixed inset-x-0 z-50 border-t border-border bg-surface/98 shadow-lg backdrop-blur-md animate-slide-up md:inset-x-auto md:right-4 md:bottom-4 md:w-[28rem] md:rounded-xl md:border"
      role="dialog"
      aria-label="Operation progress"
      aria-live="polite"
    >
      <div className="px-4 pt-3 pb-2">
        <div
          className="mx-auto mb-3 h-1 w-10 rounded-full bg-border md:hidden"
          aria-hidden
        />
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <p className="font-pixel text-sm text-text truncate">
              {operationTitle(op?.type)}
            </p>
            <p className="text-xs text-muted">
              #{operationId} · {statusLabel}
              {activeStep ? ` · ${activeStep.label}` : ""}
            </p>
          </div>
          <Button variant="ghost" onClick={onClose} aria-label="Close progress">
            {done ? "Close" : "Hide"}
          </Button>
        </div>

        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-border"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={done && status === "succeeded" ? 100 : progress}
        >
          <div
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              status === "failed" || status === "rolled_back"
                ? "bg-danger"
                : "bg-primary"
            }`}
            style={{
              width: `${done && status === "succeeded" ? 100 : Math.max(progress, status === "running" ? 8 : 2)}%`,
            }}
          />
        </div>
      </div>

      <ol className="space-y-3 px-4 py-3 max-h-[40vh] overflow-y-auto sm:max-h-64">
        {steps.map((step, index) => (
          <StepRow key={step.id} step={step} index={index} />
        ))}
      </ol>

      <div className="border-t border-border px-4 py-2 flex items-center justify-between gap-2">
        <button
          type="button"
          className="text-xs text-muted underline-offset-2 hover:underline"
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Hide log" : "Show log"}
        </button>
        {op?.rollback_performed ? (
          <p className="text-xs text-warning">Automatic rollback ran.</p>
        ) : null}
      </div>

      {expanded ? (
        <pre
          ref={logRef}
          className="max-h-40 overflow-auto border-t border-border px-4 py-3 text-xs leading-relaxed text-muted whitespace-pre-wrap font-mono"
        >
          {op?.log || "Waiting for progress…"}
        </pre>
      ) : null}
    </div>
  );
}
