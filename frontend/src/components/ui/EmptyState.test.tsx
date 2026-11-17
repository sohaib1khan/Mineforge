import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders title, description, and action", () => {
    render(
      <EmptyState
        title="Nothing here"
        description="Add an item to get started."
        action={<button type="button">Add</button>}
      />,
    );

    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Add an item to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add" })).toBeInTheDocument();
  });
});
