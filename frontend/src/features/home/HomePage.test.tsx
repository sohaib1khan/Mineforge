import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthContext";
import { HomePage } from "./HomePage";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
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
    fetchServerStatus: vi.fn(async () => ({
      container: {
        name: "bedrock",
        exists: true,
        running: true,
        status: "running",
        image: "itzg/minecraft-bedrock-server:test",
        started_at: "2026-01-01T00:00:00Z",
        uptime_seconds: 120,
      },
      level_name: "TestWorld",
      players_online: [],
      player_count: 0,
      properties_present: true,
    })),
    fetchMetricsDashboard: vi.fn(async () => ({
      latest: {
        id: 1,
        ts: "2026-01-01T00:00:00Z",
        cpu_pct: 4.2,
        mem_bytes: 128 * 1024 * 1024,
        mem_limit_bytes: 1024 * 1024 * 1024,
        net_rx_bytes: 0,
        net_tx_bytes: 0,
        players_online: 0,
      },
      playtime_week: [{ gamertag: "player_one", seconds: 3600, hours: 1 }],
      disk: { worlds_bytes: 1000, backups_bytes: 2000, backup_count: 1 },
      players_online: 0,
    })),
  };
});

describe("HomePage", () => {
  it("renders the dashboard heading and status", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={client}>
        <AuthProvider>
          <MemoryRouter>
            <HomePage />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Online")).toBeInTheDocument();
  });
});
