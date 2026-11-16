/**
 * Settings → Voice picker (mockup: docs/mockups/voice-picker-v1.html, option B).
 *
 * The default voice (Samantha) is pinned at the top. Gender and
 * Lifelike/Artificial filters, a search box and an "All languages" toggle
 * narrow the list, and each row has a ▶ preview. Voices come from
 * `voice_list_tts_voices` ({name, label, locale, gender, kind, is_default});
 * gender/kind classification lives in desktop/src-tauri/src/voice/tts.rs.
 */
import { useEffect, useMemo, useRef, useState } from "react";

export const DEFAULT_VOICE_NAME = "Samantha";
const PREVIEW_TEXT = "Hi, I'm Rigel. Standing by.";

const GROUPS = [
  { gender: "F", kind: "lifelike", sym: "♀", label: "Female · Lifelike" },
  { gender: "M", kind: "lifelike", sym: "♂", label: "Male · Lifelike" },
  { gender: "U", kind: "lifelike", sym: "◦", label: "Other · Lifelike" },
  { gender: "F", kind: "artificial", sym: "♀", label: "Female · Artificial" },
  { gender: "M", kind: "artificial", sym: "♂", label: "Male · Artificial" },
  { gender: "U", kind: "artificial", sym: "◦", label: "Other · Artificial" },
  { gender: "U", kind: "novelty", sym: "✦", label: "Novelty · effects" },
];

const isEnglish = (v) => v.locale.startsWith("en");

/** en_GB → "GB"; it_IT → "it-IT"; ar_001 → "ar". */
export function localeTag(locale) {
  const [lang, region] = locale.split("_");
  if (lang === "en" && region) return region;
  return region && !/^\d+$/.test(region) ? `${lang}-${region}` : lang;
}

function Seg({ value, options, onChange }) {
  return (
    <div className="vp-seg">
      {options.map(([v, text]) => (
        <button key={v} className={value === v ? "on" : ""} onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}

export default function VoicePicker({ voices, value, onChange, onPreview }) {
  const [open, setOpen] = useState(false);
  const [gender, setGender] = useState("all");
  const [kind, setKind] = useState("all");
  const [query, setQuery] = useState("");
  const [allLanguages, setAllLanguages] = useState(false);
  const [playing, setPlaying] = useState(null);
  const rootRef = useRef(null);

  const defaultVoice =
    voices.find((v) => v.is_default) || voices.find((v) => v.name === DEFAULT_VOICE_NAME);
  const selectedName = value || defaultVoice?.name || DEFAULT_VOICE_NAME;
  const selected = voices.find((v) => v.name === selectedName);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    const onClick = (e) => rootRef.current && !rootRef.current.contains(e.target) && setOpen(false);
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [open]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    return GROUPS.filter(
      (g) =>
        (gender === "all" || g.gender === gender) &&
        (kind === "all" ||
          (kind === "artificial" ? g.kind !== "lifelike" : g.kind === kind))
    )
      .map((g) => ({
        ...g,
        items: voices.filter(
          (v) =>
            v.gender === g.gender &&
            v.kind === g.kind &&
            (allLanguages || isEnglish(v)) &&
            (q ? v.name.toLowerCase().includes(q) : !v.is_default)
        ),
      }))
      .filter((g) => g.items.length > 0);
  }, [voices, gender, kind, query, allLanguages]);

  function choose(v) {
    onChange(v.name);
    setOpen(false);
  }

  function preview(e, v) {
    e.stopPropagation();
    setPlaying(v.name);
    setTimeout(() => setPlaying((p) => (p === v.name ? null : p)), 1500);
    onPreview?.(v.name, PREVIEW_TEXT);
  }

  function Row({ v, pinned }) {
    const isSel = v.name === selectedName;
    return (
      <div
        className={`vp-opt${isSel ? " sel" : ""}${pinned ? " pinned" : ""}${
          playing === v.name ? " playing" : ""
        }`}
        onClick={() => choose(v)}
        role="option"
        aria-selected={isSel}
      >
        <span className="vp-tick">{isSel ? "✓" : ""}</span>
        <span>{v.label}</span>
        <span className="vp-acc">{localeTag(v.locale)}</span>
        {v.name.includes("(Enhanced)") && <span className="vp-badge">Enhanced</span>}
        {v.name.includes("(Premium)") && <span className="vp-badge">Premium</span>}
        {pinned && <span className="vp-badge def">Default</span>}
        <button className="vp-play" title="Preview" onClick={(e) => preview(e, v)}>
          ▶
        </button>
      </div>
    );
  }

  const count = groups.reduce((n, g) => n + g.items.length, 0);
  // The pinned default follows the filters too: no ♀ Samantha under "♂ Male".
  const defaultMatchesFilters =
    defaultVoice &&
    (gender === "all" || defaultVoice.gender === gender) &&
    (kind === "all" ||
      (kind === "artificial" ? defaultVoice.kind !== "lifelike" : defaultVoice.kind === kind));

  return (
    <div className={`vp${open ? " open" : ""}`} ref={rootRef}>
      <button className="vp-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span>{selected?.label || selectedName}</span>
        {selected && <span className="vp-acc">{localeTag(selected.locale)}</span>}
        {selected?.is_default && <span className="vp-badge def">Default</span>}
        <span className="vp-caret">▾</span>
      </button>

      {open && (
        <div className="vp-menu" role="listbox">
          <div className="vp-filters">
            <Seg
              value={gender}
              onChange={setGender}
              options={[["all", "All"], ["F", "♀ Female"], ["M", "♂ Male"]]}
            />
            <Seg
              value={kind}
              onChange={setKind}
              options={[["all", "All"], ["lifelike", "Lifelike"], ["artificial", "Artificial"]]}
            />
            <input
              className="vp-search"
              placeholder="Search…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              autoFocus
            />
            <label className="vp-lang">
              <input
                type="checkbox"
                checked={allLanguages}
                onChange={(e) => setAllLanguages(e.target.checked)}
              />
              All languages
            </label>
          </div>
          <div className="vp-list">
            {!query && defaultVoice && defaultMatchesFilters && <Row v={defaultVoice} pinned />}
            {groups.map((g) => (
              <div key={`${g.gender}-${g.kind}`}>
                <div className="vp-group">
                  <span className="vp-sym">{g.sym}</span>
                  {g.label}
                  <span className="vp-ct">{g.items.length}</span>
                </div>
                {g.items.map((v) => (
                  <Row key={v.name} v={v} />
                ))}
              </div>
            ))}
            {count === 0 && query && <div className="vp-empty">No voices match.</div>}
          </div>
          <p className="vp-more">
            Want more natural voices? Download <i>Enhanced</i> or <i>Premium</i> ones in System
            Settings → Accessibility → Spoken Content → System Voice → Manage Voices. They show
            up under Lifelike.
          </p>
        </div>
      )}
    </div>
  );
}
