import { describe, expect, it } from "vitest";

import { formatErrorDetail } from "./api";

describe("formatErrorDetail", () => {
  it("passes through string details", () => {
    expect(formatErrorDetail("Nope")).toBe("Nope");
  });

  it("formats pydantic validation lists", () => {
    const detail = [
      {
        type: "string_pattern_mismatch",
        loc: ["body", "username"],
        msg: "String should match pattern",
      },
    ];
    expect(formatErrorDetail(detail)).toBe("username: String should match pattern");
  });

  it("does not render [object Object]", () => {
    const text = formatErrorDetail([{ msg: "bad", loc: ["body", "password"] }]);
    expect(text).toBe("password: bad");
    expect(text).not.toContain("[object Object]");
  });
});
