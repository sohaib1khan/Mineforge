import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import {
  ApiError,
  fetchConsoleHistory,
  fetchServerStatus,
  sendConsoleCommand,
} from "../../lib/api";
import { useAuth } from "../auth/AuthContext";

type Line = { ts: string; stream: string; text: string };

export function ConsolePage() {
  const { user } = useAuth();
  const [lines, setLines] = useState<Line[]>([]);
  const [command, setCommand] = useState("");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const statusQuery = useQuery({
    queryKey: ["server-status"],
    queryFn: fetchServerStatus,
    refetchInterval: 10_000,
  });

  useQuery({
    queryKey: ["console-history"],
    queryFn: async () => {
      const data = await fetchConsoleHistory();
      setLines(data.lines);
      return data;
    },
  });

  useEffect(() => {
    if (user?.role !== "admin") return;
    const source = new EventSource("/api/console/stream", { withCredentials: true });
    source.onmessage = (event) => {
      try {
        const line = JSON.parse(event.data) as Line;
        setLines((prev) => [...prev.slice(-400), line]);
      } catch {
        // ignore malformed
      }
    };
    source.onerror = () => {
      // Browser will retry EventSource automatically.
    };
    return () => source.close();
  }, [user?.role]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  if (user?.role !== "admin") {
    return <p className="text-danger">Admin access required.</p>;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await sendConsoleCommand(command);
      setCommand("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Send failed");
    }
  }

  const online = statusQuery.data?.players_online ?? [];

  return (
    <section className="space-y-4">
      <div className="space-y-1">
        <h1 className="font-pixel text-2xl">Console</h1>
        <p className="text-sm text-muted">
          Live Bedrock output. Online players (pick for op/give):{" "}
          {online.length === 0 ? "none" : online.map((p) => p.gamertag).join(", ")}
        </p>
      </div>

      <div
        className="h-[50vh] overflow-y-auto rounded-md border border-border bg-[#121518] p-3 font-mono text-xs text-[#d7dde2]"
        role="log"
        aria-live="polite"
      >
        {lines.map((line, index) => (
          <div key={`${line.ts}-${index}`} className="whitespace-pre-wrap">
            <span className="text-[#6f8f6a]">{line.stream}</span> {line.text}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form className="flex flex-wrap gap-2 items-end" onSubmit={onSubmit}>
        <div className="flex-1 min-w-[12rem]">
          <Input
            label="Command"
            name="command"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder="list"
            required
          />
        </div>
        <Button type="submit">Send</Button>
        <Button type="button" variant="secondary" onClick={() => setCommand("list")}>
          list
        </Button>
      </form>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </section>
  );
}
