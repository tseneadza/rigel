/**
 * Global toggle hotkey for expanding/minimizing the orb — Cmd+Shift+R.
 * In the native app this is a true OS-level global shortcut (fires even
 * when Rigel isn't focused). Outside Tauri (plain browser/dev preview,
 * where the global-shortcut plugin can't function) it falls back to a
 * window-scoped keydown listener for the same combo, so the toggle is
 * still testable there while the window has focus.
 */
const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

const ACCELERATOR = "CmdOrCtrl+Shift+R";

export function installToggleHotkey(onToggle) {
  if (isTauri()) {
    let cancelled = false;
    import("@tauri-apps/plugin-global-shortcut").then(({ register }) => {
      if (cancelled) return;
      register(ACCELERATOR, (event) => {
        if (event.state === "Pressed") onToggle();
      }).catch((err) => console.error("Failed to register toggle hotkey:", err));
    });
    return () => {
      cancelled = true;
      import("@tauri-apps/plugin-global-shortcut").then(({ unregister }) =>
        unregister(ACCELERATOR).catch(() => {})
      );
    };
  }

  function handleKeydown(e) {
    if (e.shiftKey && (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "r") {
      e.preventDefault();
      onToggle();
    }
  }
  window.addEventListener("keydown", handleKeydown);
  return () => window.removeEventListener("keydown", handleKeydown);
}
