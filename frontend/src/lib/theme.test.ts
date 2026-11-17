import { afterEach, describe, expect, it } from "vitest";

import { applyTheme, readStoredTheme, THEME_KEY, toggleTheme } from "./theme";

afterEach(() => {
  localStorage.removeItem(THEME_KEY);
  document.documentElement.removeAttribute("data-theme");
});

describe("theme helpers", () => {
  it("defaults to dark when nothing is stored", () => {
    expect(readStoredTheme()).toBe("dark");
  });

  it("applies and persists light theme", () => {
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    expect(readStoredTheme()).toBe("light");
  });

  it("toggles between dark and light", () => {
    expect(toggleTheme("dark")).toBe("light");
    expect(toggleTheme("light")).toBe("dark");
  });
});
