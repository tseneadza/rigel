import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ConversationControls from "../components/ConversationControls.jsx";
import HistoryPanel from "../components/HistoryPanel.jsx";

vi.mock("../api.js", () => ({
  getConversationTurns: vi.fn(() =>
    Promise.resolve({
      turns: [
        { id: 1, role: "user", text: "My sister is Priya." },
        { id: 2, role: "rigel", text: "Got it." },
      ],
    })
  ),
}));

describe("ConversationControls", () => {
  it("labels mute when listening and unmute when muted", () => {
    const { rerender } = render(
      <ConversationControls micOn onToggleMic={() => {}} onNewChat={() => {}}
        historyOpen={false} onToggleHistory={() => {}} />
    );
    expect(screen.getByRole("button", { name: "Mute Rigel's ears" })).toBeTruthy();
    rerender(
      <ConversationControls micOn={false} onToggleMic={() => {}} onNewChat={() => {}}
        historyOpen={false} onToggleHistory={() => {}} />
    );
    expect(screen.getByRole("button", { name: "Unmute Rigel's ears" }).className).toContain("icon-btn--muted");
  });

  it("calls the handlers for mute, New Chat and History", () => {
    const onToggleMic = vi.fn();
    const onNewChat = vi.fn();
    const onToggleHistory = vi.fn();
    render(
      <ConversationControls micOn onToggleMic={onToggleMic} onNewChat={onNewChat}
        historyOpen={false} onToggleHistory={onToggleHistory} />
    );
    fireEvent.click(screen.getByRole("button", { name: "Mute Rigel's ears" }));
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    fireEvent.click(screen.getByRole("button", { name: "Chat history" }));
    expect(onToggleMic).toHaveBeenCalledTimes(1);
    expect(onNewChat).toHaveBeenCalledTimes(1);
    expect(onToggleHistory).toHaveBeenCalledTimes(1);
  });
});

describe("HistoryPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists conversations and loads a past transcript read-only", async () => {
    render(
      <HistoryPanel
        conversations={[
          { id: 2, title: null, turn_count: 0 },
          { id: 1, title: "Earlier conversation", turn_count: 2 },
        ]}
        activeId={2}
        onClose={() => {}}
      />
    );
    expect(screen.getByText(/Current chat/)).toBeTruthy();
    expect(screen.getByText("Nothing is deleted.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Earlier conversation/ }));
    await waitFor(() => expect(screen.getByText(/My sister is Priya\./)).toBeTruthy());
    expect(screen.getByText(/Got it\./)).toBeTruthy();
  });
});
