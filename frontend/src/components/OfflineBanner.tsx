import { useEffect, useState } from "react";

export function OfflineBanner() {
  const [offline, setOffline] = useState(!navigator.onLine);
  const [serverDown, setServerDown] = useState(false);

  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);

    let cancelled = false;
    const ping = async () => {
      if (!navigator.onLine) {
        setServerDown(false);
        return;
      }
      try {
        const res = await fetch("/api/health", {
          method: "GET",
          cache: "no-store",
          credentials: "same-origin",
        });
        if (!cancelled) setServerDown(!res.ok);
      } catch {
        if (!cancelled) setServerDown(true);
      }
    };
    void ping();
    const id = window.setInterval(() => void ping(), 20_000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  if (!offline && !serverDown) {
    return null;
  }

  return (
    <div
      className="border-b border-warning/40 bg-warning/15 px-4 py-2 text-center text-sm text-text"
      role="status"
    >
      {offline
        ? "You are offline. The app shell still works; server actions will fail until you reconnect."
        : "Server unreachable. Check that MineForge is running, then try again."}
    </div>
  );
}
