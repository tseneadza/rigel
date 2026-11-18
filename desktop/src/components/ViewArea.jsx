/**
 * ViewArea — the main content area for non-chat views (PRD v6 FR-3, FR-4).
 * Placeholders for P1: the live ToolBox graphic and Rigel's presentation
 * content are not wired yet.
 */
export default function ViewArea({ view }) {
  if (view === "toolbox") {
    return (
      <section className="view-area" aria-label="Toolbox view">
        <h2>ToolBox</h2>
        <p>The live ToolBox graphic is not wired yet.</p>
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
