import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TaskBoard } from "./TaskBoard";

describe("TaskBoard", () => {
  it("uses a mobile-first stacked layout (no horizontal scroll) with responsive kanban columns on larger screens", () => {
    render(
      <TaskBoard
        tasks={[
          {
            id: "t1",
            title: "Inbox item",
            status: "inbox",
            priority: "medium",
          },
        ]}
      />,
    );

    const board = screen.getByTestId("task-board");

    expect(board.className).toContain("overflow-x-hidden");
    expect(board.className).toContain("sm:overflow-x-auto");
    expect(board.className).toContain("grid-cols-1");
    expect(board.className).toContain("sm:grid-flow-col");
  });

  it("only sticks column headers on larger screens (avoids weird stacked sticky headers on mobile)", () => {
    render(
      <TaskBoard
        tasks={[
          {
            id: "t1",
            title: "Inbox item",
            status: "inbox",
            priority: "medium",
          },
        ]}
      />,
    );

    const header = screen
      .getByRole("heading", { name: "Inbox" })
      .closest(".column-header");
    expect(header?.className).toContain("sm:sticky");
    expect(header?.className).toContain("sm:top-0");
    // Ensure we didn't accidentally keep unscoped sticky behavior.
    expect(header?.className).not.toContain("sticky top-0");
  });

  it("shows blocked-by-missing-spec badge", () => {
    render(
      <TaskBoard
        tasks={[
          {
            id: "1",
            title: "T",
            status: "inbox",
            priority: "medium",
            gsd_stage: "plan",
            spec_doc_ref: null,
            plan_doc_ref: "p",
          },
        ]}
      />,
    );
    expect(screen.getByText(/missing spec/i)).toBeInTheDocument();
  });

  it("shows notebook gate badges and filters notebook blocked/retryable tasks", () => {
    render(
      <TaskBoard
        tasks={[
          {
            id: "t-blocked",
            title: "Notebook blocked task",
            status: "inbox",
            priority: "medium",
            task_mode: "notebook",
            notebook_gate_state: "misconfig",
            notebook_gate_reason: "invalid_profile",
          },
          {
            id: "t-retry",
            title: "Notebook retry task",
            status: "inbox",
            priority: "medium",
            task_mode: "notebook",
            notebook_gate_state: "retryable",
            notebook_gate_reason: "auth_expired",
          },
          {
            id: "t-standard",
            title: "Standard task",
            status: "inbox",
            priority: "low",
            task_mode: "standard",
          },
        ]}
      />,
    );

    expect(
      screen.getByText(/notebook blocked - invalid_profile/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/notebook retryable - auth_expired/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /blocked - 1/i }));
    expect(screen.getByText("Notebook blocked task")).toBeInTheDocument();
    expect(screen.queryByText("Notebook retry task")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retryable - 1/i }));
    expect(screen.getByText("Notebook retry task")).toBeInTheDocument();
    expect(screen.queryByText("Notebook blocked task")).not.toBeInTheDocument();
    expect(screen.queryByText("Standard task")).not.toBeInTheDocument();
  });
});
