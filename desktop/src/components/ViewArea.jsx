/**
 * ViewArea — the main content area for non-chat views (PRD v6 FR-3, FR-4).
 * Toolbox shows the live ToolBox map (M2 v2). Presentation is still a placeholder.
 */
import ToolBoxMap from "./ToolBoxMap.jsx";
export default function ViewArea({ view, toolbox }) {
  if (view === "toolbox") {
    return (
      <section className="view-area" aria-label="Toolbox view">
        <ToolBoxMap
          serverRows={toolbox?.serverRows ?? []}
          mode={toolbox?.mode ?? "2d"}
          fallbackReason={toolbox?.fallbackReason ?? null}
          hubState={toolbox?.hubState ?? "offline"}
        />
      </section>
    );
  }
  if (view === "presentation") {
    return (
      <section className="view-area" aria-label="Presentation view">
        <h2>Presentation</h2>
        <p>Rigel hasn't presented anything yet.</p>
      </section>
    );
  }
  return null;
}
