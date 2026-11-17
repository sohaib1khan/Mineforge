import { NavLink, Outlet } from "react-router-dom";

import { OfflineBanner } from "../components/OfflineBanner";
import { Button } from "../components/ui/Button";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../features/theme/ThemeContext";
import { APP_DISPLAY_NAME, AUTHOR_NAME, AUTHOR_URL } from "./constants";

type NavItem = {
  to: string;
  label: string;
  end?: boolean;
  adminOnly?: boolean;
  mobilePrimary?: boolean;
};

const NAV: NavItem[] = [
  { to: "/", label: "Home", end: true, mobilePrimary: true },
  { to: "/worlds", label: "Worlds", mobilePrimary: true },
  { to: "/addons", label: "Add-ons", mobilePrimary: true },
  { to: "/backups", label: "Backups" },
  { to: "/metrics", label: "Metrics", mobilePrimary: true },
  { to: "/help", label: "Help" },
  { to: "/server", label: "Server", adminOnly: true },
  { to: "/console", label: "Console", adminOnly: true },
  { to: "/users", label: "Users", adminOnly: true },
  { to: "/account", label: "Account", mobilePrimary: true },
];

const desktopLinkClass = ({ isActive }: { isActive: boolean }) =>
  `min-h-11 w-full inline-flex items-center rounded-md px-3 text-sm transition-colors duration-[var(--motion-fast)] ${
    isActive
      ? "bg-primary/15 text-primary"
      : "text-muted hover:bg-border/40 hover:text-text"
  }`;

const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-12 min-w-0 flex-1 flex-col items-center justify-center gap-0.5 px-1 text-[11px] transition-colors duration-[var(--motion-fast)] ${
    isActive ? "text-primary" : "text-muted"
  }`;

export function AppShell() {
  const { user, logout, needsSetup } = useAuth();
  const { theme, toggle } = useTheme();
  const isAdmin = user?.role === "admin";

  const visible = NAV.filter((item) => !item.adminOnly || isAdmin);
  const mobilePrimary = visible.filter((item) => item.mobilePrimary);

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
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="shrink-0 space-y-2 border-t border-border bg-surface/95 p-3">
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={toggle}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? "Light theme" : "Dark theme"}
            </Button>
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={() => void logout()}
            >
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
              <Button
                variant="ghost"
                onClick={toggle}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              >
                {theme === "dark" ? "Light" : "Dark"}
              </Button>
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
                  <span className="font-medium">{item.label}</span>
                </NavLink>
              ))}
            </div>
          </nav>
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
