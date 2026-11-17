import { describe, expect, it } from "vitest";

import { downsample, formatBytes, formatHours } from "./format";

describe("metrics format helpers", () => {
  it("formats bytes and hours", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatHours(45)).toBe("45s");
    expect(formatHours(120)).toBe("2m");
    expect(formatHours(7200)).toBe("2.0h");
  });

  it("downsamples while keeping the last point", () => {
    const items = Array.from({ length: 10 }, (_, i) => i);
    const out = downsample(items, 3);
    expect(out.length).toBeLessThanOrEqual(4);
    expect(out[out.length - 1]).toBe(9);
  });
});
