import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({ getLlmConfig: vi.fn() }));

import { getLlmConfig } from "../api.js";
import BrainChip, { describeBrain } from "../components/BrainChip.jsx";

describe("describeBrain", () => {
  it("labels the built-in stub brain as local", () => {
    expect(describeBrain({ provider: "stub" })).toBe("Basic · built-in · Local");
    expect(describeBrain(null)).toBe("Basic · built-in · Local");
  });

  it("labels Claude as cloud with its model", () => {
    expect(describeBrain({ provider: "claude", claude_model: "claude-haiku-5-5" })).toBe(
      "Claude · claude-haiku-5-5 · Cloud",
    );
  });

  it("labels Ollama on loopback as local", () => {
    expect(
      describeBrain({ provider: "ollama", ollama_model: "llama3", ollama_host: "http://127.0.0.1:11434" }),
    ).toBe("Ollama · llama3 · Local");
    expect(describeBrain({ provider: "ollama", ollama_model: "llama3", ollama_host: "localhost:11434" })).toBe(
      "Ollama · llama3 · Local",
    );
  });

  it("labels Ollama on another host as network", () => {
    expect(
      describeBrain({ provider: "ollama", ollama_model: "llama3", ollama_host: "http://192.168.1.20:11434" }),
    ).toBe("Ollama · llama3 · Network");
  });
});

describe("BrainChip", () => {
  beforeEach(() => {
    getLlmConfig.mockReset();
  });

  it("shows checking while the config loads, then the brain label", async () => {
    getLlmConfig.mockResolvedValue({ provider: "stub" });
    render(<BrainChip />);
    expect(screen.getByText("Brain · checking…")).toBeInTheDocument();
    expect(await screen.findByText("Basic · built-in · Local")).toBeInTheDocument();
  });

  it("shows unavailable when the sidecar cannot be reached", async () => {
    getLlmConfig.mockRejectedValue(new Error("sidecar down"));
    render(<BrainChip />);
    expect(await screen.findByText("Brain · unavailable")).toBeInTheDocument();
  });
});
