import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  applyTheme,
  readStoredTheme,
  toggleTheme,
  type ThemeMode,
} from "../../lib/theme";

type ThemeApi = {
  theme: ThemeMode;
  setTheme: (mode: ThemeMode) => void;
  toggle: () => void;
};

const ThemeContext = createContext<ThemeApi | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(() => readStoredTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((mode: ThemeMode) => {
    applyTheme(mode);
    setThemeState(mode);
  }, []);

  const toggle = useCallback(() => {
    setThemeState((current) => toggleTheme(current));
  }, []);

  const api = useMemo(() => ({ theme, setTheme, toggle }), [theme, setTheme, toggle]);

  return <ThemeContext.Provider value={api}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeApi {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return ctx;
}
