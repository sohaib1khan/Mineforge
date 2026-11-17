import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { ToastProvider } from "../components/ui/Toast";
import { AccountPage } from "../features/account/AccountPage";
import { AddonsPage } from "../features/addons/AddonsPage";
import { AuthProvider } from "../features/auth/AuthContext";
import { LoginPage } from "../features/auth/LoginPage";
import { BackupsPage } from "../features/backups/BackupsPage";
import { ConsolePage } from "../features/console/ConsolePage";
import { HelpPage } from "../features/help/HelpPage";
import { HomePage } from "../features/home/HomePage";
import { MetricsPage } from "../features/metrics/MetricsPage";
import { ServerPage } from "../features/server/ServerPage";
import { SetupPage } from "../features/setup/SetupPage";
import { StreamPage } from "../features/stream/StreamPage";
import { ThemeProvider } from "../features/theme/ThemeContext";
import { UsersPage } from "../features/users/UsersPage";
import { WorldsPage } from "../features/worlds/WorldsPage";
import { AppShell } from "./AppShell";
import { PublicOnly, RequireAdmin, RequireAuth, SetupOnly } from "./RequireAuth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>
            <BrowserRouter>
              <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-surface focus:px-3 focus:py-2 focus:text-sm focus:shadow-lg"
              >
                Skip to content
              </a>
              <Routes>
                <Route element={<AppShell />}>
                  <Route element={<SetupOnly />}>
                    <Route path="/setup" element={<SetupPage />} />
                  </Route>
                  <Route element={<PublicOnly />}>
                    <Route path="/login" element={<LoginPage />} />
                  </Route>
                  <Route element={<RequireAuth />}>
                    <Route index element={<HomePage />} />
                    <Route path="/account" element={<AccountPage />} />
                    <Route path="/backups" element={<BackupsPage />} />
                    <Route path="/metrics" element={<MetricsPage />} />
                    <Route path="/help" element={<HelpPage />} />
                    <Route path="/worlds" element={<WorldsPage />} />
                    <Route path="/addons" element={<AddonsPage />} />
                    <Route path="/stream" element={<StreamPage />} />
                    <Route element={<RequireAdmin />}>
                      <Route path="/server" element={<ServerPage />} />
                      <Route path="/console" element={<ConsolePage />} />
                      <Route path="/users" element={<UsersPage />} />
                    </Route>
                  </Route>
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </BrowserRouter>
          </AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
