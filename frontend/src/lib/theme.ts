export type ThemeMode = "dark" | "light";

export const THEME_KEY = "mineforge-theme";

export function readStoredTheme(): ThemeMode {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function applyTheme(mode: ThemeMode): void {
  document.documentElement.setAttribute("data-theme", mode);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", mode === "light" ? "#EEF2F4" : "#1E2226");
  }
  try {
    localStorage.setItem(THEME_KEY, mode);
  } catch {
    // ignore private mode failures
  }
}

export function toggleTheme(current: ThemeMode): ThemeMode {
  const next: ThemeMode = current === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}
