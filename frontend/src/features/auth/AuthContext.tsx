import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchMe,
  fetchSetupStatus,
  login as apiLogin,
  logout as apiLogout,
  setCsrfToken,
} from "../../lib/api";
import type { MeResponse, UserPublic } from "../../lib/types";

type AuthContextValue = {
  user: UserPublic | null;
  csrfToken: string | null;
  needsSetup: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [bootstrapped, setBootstrapped] = useState(false);

  const setupQuery = useQuery({
    queryKey: ["setup-status"],
    queryFn: fetchSetupStatus,
  });

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    retry: false,
    enabled: setupQuery.isSuccess && !setupQuery.data.needs_setup,
  });

  useEffect(() => {
    if (setupQuery.isError || setupQuery.isSuccess) {
      if (setupQuery.data?.needs_setup) {
        setCsrfToken(null);
        setBootstrapped(true);
        return;
      }
    }
    if (meQuery.isFetched || meQuery.isError || setupQuery.data?.needs_setup) {
      setBootstrapped(true);
    }
  }, [
    setupQuery.isError,
    setupQuery.isSuccess,
    setupQuery.data,
    meQuery.isFetched,
    meQuery.isError,
  ]);

  useEffect(() => {
    if (meQuery.data) {
      setCsrfToken(meQuery.data.csrf_token);
    }
    if (meQuery.isError) {
      setCsrfToken(null);
    }
  }, [meQuery.data, meQuery.isError]);

  const login = useCallback(
    async (username: string, password: string) => {
      const me = await apiLogin({ username, password });
      queryClient.setQueryData<MeResponse>(["me"], me);
      await queryClient.invalidateQueries({ queryKey: ["setup-status"] });
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setCsrfToken(null);
      queryClient.setQueryData(["me"], null);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
    }
  }, [queryClient]);

  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["me"] });
    await queryClient.invalidateQueries({ queryKey: ["setup-status"] });
  }, [queryClient]);

  const user = meQuery.data?.user ?? null;
  const needsSetup = Boolean(setupQuery.data?.needs_setup);
  const isLoading =
    !bootstrapped || setupQuery.isLoading || (!needsSetup && meQuery.isLoading);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      csrfToken: meQuery.data?.csrf_token ?? null,
      needsSetup,
      isLoading,
      login,
      logout,
      refresh,
    }),
    [user, meQuery.data?.csrf_token, needsSetup, isLoading, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
