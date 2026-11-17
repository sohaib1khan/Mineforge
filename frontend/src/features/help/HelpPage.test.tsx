import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthContext";
import { ThemeProvider } from "../theme/ThemeContext";
import { HelpPage } from "./HelpPage";

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
    fetchHelpGuides: vi.fn(async () => ({
      guides: [
        {
          slug: "connecting",
          title: "Connecting from phone and PC",
          summary: "Join on TCP 19132.",
          order: 10,
        },
      ],
    })),
    fetchHelpGuide: vi.fn(async () => ({
      slug: "connecting",
      title: "Connecting from phone and PC",
      summary: "Join on TCP 19132.",
      markdown: "# Connecting\n\nUse port **19132**.",
    })),
  };
});

describe("HelpPage", () => {
  it("renders guide list and markdown body", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={client}>
        <ThemeProvider>
          <AuthProvider>
            <MemoryRouter>
              <HelpPage />
            </MemoryRouter>
          </AuthProvider>
        </ThemeProvider>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Help" })).toBeInTheDocument();
    expect(
      await screen.findByRole("button", {
        name: "Connecting from phone and PC",
      }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Connecting" }),
    ).toBeInTheDocument();
  });
});
