import { useEffect, useState } from "react";
import { getLlmConfig } from "../api.js";

/**
 * BrainChip — which brain answers, and whether it runs in the cloud or locally
 * (PRD v6 FR-29 / FR-30). Read-only for now; the click-to-Settings and
 * fallback state (FR-31 / FR-32) come in a later slice.
 */
const LOOPBACK = /^(https?:\/\/)?(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/|$)/i;

export function describeBrain(cfg) {
  if (!cfg || !cfg.provider || cfg.provider === "stub") {
    return "Basic · built-in · Local";
  }
  if (cfg.provider === "claude") {
    return `Claude · ${cfg.claude_model} · Cloud`;
  }
  if (cfg.provider === "ollama") {
    const where = LOOPBACK.test(cfg.ollama_host || "") ? "Local" : "Network";
    return `Ollama · ${cfg.ollama_model} · ${where}`;
  }
  return `${cfg.provider} · Local`;
}

export default function BrainChip() {
  // undefined = still loading, null = sidecar unreachable.
  const [cfg, setCfg] = useState(undefined);

  useEffect(() => {
    let alive = true;
    getLlmConfig()
      .then((c) => alive && setCfg(c))
      .catch(() => alive && setCfg(null));
    return () => {
      alive = false;
    };
  }, []);

  const label =
    cfg === undefined ? "Brain · checking…" : cfg === null ? "Brain · unavailable" : describeBrain(cfg);

  return (
    <div className="brain-chip" title="The brain that answers chat turns">
      <span className="brain-chip-dot" data-unavailable={cfg === null || undefined} />
      {label}
    </div>
  );
}
