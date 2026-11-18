import { describe, expect, it } from "vitest";

import { deriveOperationSteps, operationTitle } from "./operationSteps";

describe("operationSteps", () => {
  it("titles switch operations clearly", () => {
    expect(operationTitle("switch")).toBe("Switching world");
  });

  it("advances switch steps from log lines", () => {
    const log = [
      "Warning players: switching to Helixx_World in 30s",
      "Countdown: 25s",
      "Pre-switch backup of Current",
      "Stopping Bedrock",
    ].join("\n");

    const steps = deriveOperationSteps("switch", log, "running");
    expect(steps.find((s) => s.id === "warn")?.state).toBe("done");
    expect(steps.find((s) => s.id === "backup")?.state).toBe("done");
    expect(steps.find((s) => s.id === "stop")?.state).toBe("active");
    expect(steps.find((s) => s.id === "warn")?.detail).toBe("25s remaining");
  });

  it("marks all steps done on success", () => {
    const log = "Switched to Helixx_World";
    const steps = deriveOperationSteps("switch", log, "succeeded");
    expect(steps.every((s) => s.state === "done")).toBe(true);
  });
});
