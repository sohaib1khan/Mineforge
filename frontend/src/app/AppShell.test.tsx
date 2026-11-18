import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ToastProvider } from "../components/ui/Toast";
import { AuthProvider } from "../features/auth/AuthContext";
import { ThemeProvider } from "../features/theme/ThemeContext";
import { AppShell } from "./AppShell";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    fetchSetupStatus: vi.fn(async () => ({
      needs_setup: false,
      app_name: "MineForge",
    })),
    fetchMe: vi.fn(async () => ({
      csrf_token: "test-csrf",
      user: {
        id: 1,
        username: "admin_one",
        role: "admin",
        is_active: true,
        must_change_password: false,
        created_at: "2026-01-01T00:00:00Z",
        last_login_at: null,
      },
    })),
  };
});

describe("AppShell", () => {
  it("renders brand, skip target, and primary nav", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
      ),
    );

    render(
      <QueryClientProvider client={client}>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <MemoryRouter initialEntries={["/"]}>
                <Routes>
                  <Route element={<AppShell />}>
                    <Route index element={<p>Dashboard body</p>} />
                  </Route>
                </Routes>
              </MemoryRouter>
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByLabelText("Main")).toBeInTheDocument();
    expect(screen.getByLabelText("Mobile")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /More/i })).toBeInTheDocument();
    expect(screen.getByText("Dashboard body")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sohaib Khan" })).toHaveAttribute(
      "href",
      "https://github.com/sohaib1khan/Mineforge",
    );
    expect(document.getElementById("main-content")).not.toBeNull();

    vi.unstubAllGlobals();
  });
});
