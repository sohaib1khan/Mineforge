import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { LucideIcon } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Icon, Icons } from "../components/icons";
import { OfflineBanner } from "../components/OfflineBanner";
import { Button } from "../components/ui/Button";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../features/theme/ThemeContext";
import { fetchStreamStatus } from "../lib/api";
import { APP_DISPLAY_NAME, AUTHOR_NAME, AUTHOR_URL } from "./constants";

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  adminOnly?: boolean;
  mobilePrimary?: boolean;
};

const NAV: NavItem[] = [
  { to: "/", label: "Home", icon: Icons.Home, end: true, mobilePrimary: true },
  { to: "/stream", label: "Stream", icon: Icons.Stream, mobilePrimary: true },
  { to: "/worlds", label: "Worlds", icon: Icons.Worlds, mobilePrimary: true },
  { to: "/addons", label: "Add-ons", icon: Icons.Addons, mobilePrimary: true },
  { to: "/backups", label: "Backups", icon: Icons.Backups },
  { to: "/metrics", label: "Metrics", icon: Icons.Metrics },
  { to: "/help", label: "Help", icon: Icons.Help },
  { to: "/server", label: "Server", icon: Icons.Server, adminOnly: true },
  { to: "/console", label: "Console", icon: Icons.Console, adminOnly: true },
  { to: "/users", label: "Users", icon: Icons.Users, adminOnly: true },
  { to: "/account", label: "Account", icon: Icons.Account },
];

const desktopLinkClass = ({ isActive }: { isActive: boolean }) =>
  `min-h-11 w-full inline-flex items-center gap-2.5 rounded-md px-3 text-sm transition-colors duration-[var(--motion-fast)] ${
    isActive
      ? "mf-nav-active bg-primary/15 text-primary"
      : "text-muted hover:bg-border/40 hover:text-text"
  }`;

const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-12 min-w-0 flex-1 flex-col items-center justify-center gap-0.5 px-1 text-[11px] transition-colors duration-[var(--motion-fast)] ${
    isActive ? "text-primary" : "text-muted"
  }`;

export function AppShell() {
  const { user, logout, needsSetup } = useAuth();
  const { theme, toggle } = useTheme();
  const location = useLocation();
  const [moreOpen, setMoreOpen] = useState(false);
  const isAdmin = user?.role === "admin";
  const streamQuery = useQuery({
    queryKey: ["stream-status"],
    queryFn: fetchStreamStatus,
    enabled: Boolean(user),
    refetchInterval: 10_000,
    retry: false,
  });
  const streamLive = Boolean(streamQuery.data?.live && streamQuery.data.enabled);

  const visible = NAV.filter((item) => !item.adminOnly || isAdmin);
  const mobilePrimary = visible.filter((item) => item.mobilePrimary);
  const moreItems = visible.filter((item) => !item.mobilePrimary);

  useEffect(() => {
    setMoreOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!moreOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMoreOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [moreOpen]);

  const navLabel = (item: NavItem) => {
    if (item.to !== "/stream" || !streamLive) return item.label;
    return (
      <span className="inline-flex items-center gap-1.5">
        {item.label}
        <span
          className="mf-status-pulse h-2 w-2 rounded-full bg-danger"
          title="Live"
          aria-label="Live"
        />
      </span>
    );
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {user ? (
        <aside
          className="sticky top-0 z-30 hidden h-screen w-56 shrink-0 self-start border-r border-border bg-surface/95 md:flex md:flex-col"
          aria-label="Sidebar"
        >
          <div className="shrink-0 border-b border-border px-4 py-4">
            <p className="font-pixel text-lg tracking-wide text-primary">
              {APP_DISPLAY_NAME}
            </p>
            <p className="mt-1 truncate text-xs text-muted">{user.username}</p>
          </div>
          <nav
            className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto p-3"
            aria-label="Main"
          >
            {visible.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={desktopLinkClass}
              >
                <Icon icon={item.icon} size={16} />
                {navLabel(item)}
              </NavLink>
            ))}
          </nav>
          <div className="shrink-0 space-y-2 border-t border-border bg-surface/95 p-3">
            <Button
              variant="ghost"
              className="w-full justify-start gap-2"
              onClick={toggle}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              <Icon icon={theme === "dark" ? Icons.Sun : Icons.Moon} size={16} />
              {theme === "dark" ? "Light theme" : "Dark theme"}
            </Button>
            <Button
              variant="ghost"
              className="w-full justify-start gap-2"
              onClick={() => void logout()}
            >
              <Icon icon={Icons.Logout} size={16} />
              Sign out
            </Button>
          </div>
        </aside>
      ) : null}

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="border-b border-border bg-surface/90 px-4 py-3 md:hidden">
          <div className="flex items-center justify-between gap-3">
            <p className="font-pixel text-lg tracking-wide text-primary">
              {APP_DISPLAY_NAME}
            </p>
            {user ? (
              <p className="truncate text-xs text-muted">{user.username}</p>
            ) : null}
          </div>
        </header>

        <OfflineBanner />

        <main
          id="main-content"
          className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 page-enter pb-24 md:pb-6"
          tabIndex={-1}
        >
          <Outlet />
        </main>

        {user ? (
          <nav
            className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface/95 backdrop-blur-sm md:hidden"
            aria-label="Mobile"
          >
            <div className="mx-auto flex max-w-lg justify-around px-1 pb-[env(safe-area-inset-bottom)]">
              {mobilePrimary.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={mobileLinkClass}
                >
                  <Icon icon={item.icon} size={18} />
                  <span className="font-medium">{navLabel(item)}</span>
                </NavLink>
              ))}
              <button
                type="button"
                className={mobileLinkClass({ isActive: moreOpen })}
                aria-expanded={moreOpen}
                aria-controls="mobile-more-sheet"
                onClick={() => setMoreOpen((open) => !open)}
              >
                <Icon icon={Icons.More} size={18} />
                <span className="font-medium">More</span>
              </button>
            </div>
          </nav>
        ) : null}

        {user && moreOpen ? (
          <div className="fixed inset-0 z-50 md:hidden" role="presentation">
            <button
              type="button"
              className="absolute inset-0 bg-black/45 animate-fade-in"
              aria-label="Close menu"
              onClick={() => setMoreOpen(false)}
            />
            <div
              id="mobile-more-sheet"
              className="mf-sheet absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl border border-border bg-surface shadow-lg animate-slide-up"
              role="dialog"
              aria-modal="true"
              aria-label="More"
            >
              <div className="sticky top-0 z-10 border-b border-border bg-surface/95 px-4 pt-3 pb-2 backdrop-blur">
                <div
                  className="mx-auto mb-2 h-1 w-10 rounded-full bg-border"
                  aria-hidden
                />
                <div className="flex items-center justify-between gap-3">
                  <p className="font-pixel text-sm text-text">More</p>
                  <Button
                    variant="ghost"
                    onClick={() => setMoreOpen(false)}
                    aria-label="Close"
                  >
                    <Icon icon={Icons.Close} size={16} />
                  </Button>
                </div>
              </div>
              <nav className="grid gap-1 p-3" aria-label="More links">
                {moreItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      `flex min-h-12 items-center gap-3 rounded-lg px-3 text-sm ${
                        isActive
                          ? "bg-primary/15 text-primary"
                          : "text-text hover:bg-border/40"
                      }`
                    }
                  >
                    <Icon icon={item.icon} size={18} />
                    {item.label}
                  </NavLink>
                ))}
              </nav>
              <div className="space-y-2 border-t border-border p-3 pb-[calc(1rem+env(safe-area-inset-bottom))]">
                <Button
                  variant="secondary"
                  className="w-full justify-start gap-2"
                  onClick={toggle}
                  aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
                >
                  <Icon icon={theme === "dark" ? Icons.Sun : Icons.Moon} size={16} />
                  {theme === "dark" ? "Use light theme" : "Use dark theme"}
                </Button>
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 text-danger"
                  onClick={() => void logout()}
                >
                  <Icon icon={Icons.Logout} size={16} />
                  Sign out
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        <footer className="hidden border-t border-border px-4 py-3 text-sm text-muted md:block">
          {needsSetup ? (
            <p>Complete first-run setup to continue.</p>
          ) : (
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>
                Built by{" "}
                <a
                  href={AUTHOR_URL}
                  className="underline decoration-border underline-offset-2 hover:text-text"
                  target="_blank"
                  rel="noreferrer"
                >
                  {AUTHOR_NAME}
                </a>
              </span>
              <span aria-hidden="true">·</span>
              <span>Not affiliated with Mojang or Microsoft.</span>
            </p>
          )}
        </footer>
      </div>
    </div>
  );
}
