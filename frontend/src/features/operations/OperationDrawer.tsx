import { useEffect, useRef, useState } from "react";

import { Button } from "../../components/ui/Button";
import { fetchOperation } from "../../lib/api";
import type { OperationResponse } from "../../lib/types";

type Props = {
  operationId: number | null;
  onClose: () => void;
  onFinished?: (op: OperationResponse) => void;
};

const terminal = new Set(["succeeded", "failed", "rolled_back"]);

export function OperationDrawer({ operationId, onClose, onFinished }: Props) {
  const [op, setOp] = useState<OperationResponse | null>(null);
  const logRef = useRef<HTMLPreElement>(null);
  const finishedRef = useRef(false);

  useEffect(() => {
    finishedRef.current = false;
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

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface shadow-lg md:inset-x-auto md:right-4 md:bottom-4 md:w-[28rem] md:rounded-lg md:border"
      role="dialog"
      aria-label="Operation progress"
    >
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <p className="font-pixel text-sm text-text">
            {op?.type ?? "operation"} #{operationId}
          </p>
          <p className="text-xs text-muted capitalize">{status.replace("_", " ")}</p>
        </div>
        <Button variant="ghost" onClick={onClose} aria-label="Close progress">
          {done ? "Close" : "Hide"}
        </Button>
      </div>
      <pre
        ref={logRef}
        className="max-h-56 overflow-auto px-4 py-3 text-xs leading-relaxed text-muted whitespace-pre-wrap font-mono"
      >
        {op?.log || "Waiting for progress…"}
      </pre>
      {op?.rollback_performed ? (
        <p className="border-t border-border px-4 py-2 text-xs text-warning">
          Automatic rollback was performed.
        </p>
      ) : null}
    </div>
  );
}
