//! Text-to-speech via macOS's built-in `say`. No new dependencies, no
//! network — matches the "local execution engine" ethos and gives Rigel a
//! spoken voice with zero setup.

use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{AppHandle, Emitter, State};

/// The currently-speaking child process, if any. A new `voice_speak` call
/// kills whatever's in here before starting the next utterance, so replies
/// never overlap.
#[derive(Default)]
pub struct TtsState(pub Arc<Mutex<Option<Child>>>);

fn stop_current(state: &TtsState) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
            super::tts_finished();
        }
    }
}

#[tauri::command]
pub fn voice_speak(
    app: AppHandle,
    state: State<TtsState>,
    text: String,
    voice: Option<String>,
) -> Result<(), String> {
    stop_current(&state);

    let text = text.trim().to_string();
    if text.is_empty() {
        return Ok(());
    }

    // No saved choice means Rigel's own default voice, not whatever macOS's
    // system voice happens to be, so every caller (Settings "Test", replies,
    // approvals) sounds the same.
    let voice = voice
        .filter(|v| !v.trim().is_empty())
        .unwrap_or_else(|| DEFAULT_VOICE.to_string());
    let mut cmd = Command::new("/usr/bin/say");
    cmd.arg("-v").arg(&voice).arg(&text);

    // Deafen the wake-word listener *before* audio starts coming out of the
    // speakers, not after.
    super::tts_started();
    let child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            super::tts_finished();
            return Err(format!("failed to start `say`: {e}"));
        }
    };

    {
        let mut guard = state.0.lock().map_err(|e| e.to_string())?;
        *guard = Some(child);
    }
    let _ = app.emit("voice://state", serde_json::json!({ "state": "speaking" }));

    // Poll for completion on a background thread rather than blocking the
    // command (and thus the frontend's invoke() call) on the full utterance.
    let mutex = state.0.clone();
    let app_for_thread = app.clone();
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_millis(150));
        let mut guard = match mutex.lock() {
            Ok(g) => g,
            Err(_) => return,
        };
        match guard.as_mut() {
            Some(child) => match child.try_wait() {
                Ok(Some(_)) | Err(_) => {
                    *guard = None;
                    drop(guard);
                    super::tts_finished();
                    let _ = app_for_thread
                        .emit("voice://state", serde_json::json!({ "state": "idle" }));
                    return;
                }
                Ok(None) => continue,
            },
            // Slot was cleared by a newer voice_speak/voice_stop_speaking call;
            // that call owns emitting the next state, so this thread is done.
            None => return,
        }
    });

    Ok(())
}

#[tauri::command]
pub fn voice_stop_speaking(app: AppHandle, state: State<TtsState>) -> Result<(), String> {
    stop_current(&state);
    let _ = app.emit("voice://state", serde_json::json!({ "state": "idle" }));
    Ok(())
}

/// Rigel's default voice: Samantha, macOS's original English voice. It ships
/// with every Mac and can't be uninstalled.
pub const DEFAULT_VOICE: &str = "Samantha";

/// One installed `say` voice, for the Settings voice picker.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct TtsVoice {
    /// Exact name to pass to `say -v`, e.g. `Eddy (English (US))`.
    pub name: String,
    /// Display name without the language suffix, e.g. `Eddy`.
    pub label: String,
    /// `en_US`, `it_IT`, `ar_001`, …
    pub locale: String,
    /// `"F"`, `"M"` or `"U"` (unknown / not a person).
    pub gender: &'static str,
    /// `"lifelike"`, `"artificial"` or `"novelty"`.
    pub kind: &'static str,
    pub is_default: bool,
}

/// Sound-effect voices: not people, no gender.
const NOVELTY: &[&str] = &[
    "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Good News", "Jester",
    "Organ", "Superstar", "Trinoids", "Whisper", "Wobble", "Zarvox",
];
/// Robotic-sounding voices: the Eloquence family and the classic MacinTalk set.
const ARTIFICIAL: &[&str] = &[
    "Eddy", "Flo", "Grandma", "Grandpa", "Reed", "Rocko", "Sandy", "Shelley",
    "Albert", "Fred", "Junior", "Kathy", "Ralph",
];
/// Voice genders. macOS (AVSpeechSynthesisVoice) reports these for most human
/// voices but not the Eloquence/MacinTalk ones or voices that aren't
/// downloaded yet, so they're listed here. Anything missing shows as unknown.
const MALE: &[&str] = &[
    "Aaron", "Albert", "Aman", "Daniel", "Eddy", "Evan", "Fred", "Grandpa", "Jacques", "Jamie",
    "Junior", "Lee", "Majed", "Nathan", "Oliver", "Ralph", "Reed", "Rishi", "Rocko", "Thomas",
    "Tom", "Xander",
];
const FEMALE: &[&str] = &[
    "Alice", "Allison", "Alva", "Amira", "Amélie", "Anna", "Aru", "Ava", "Carmit", "Damayanti",
    "Daria", "Ellen", "Fiona", "Flo", "Geeta", "Grandma", "Ioana", "Isha", "Joana", "Joelle",
    "Kanya", "Karen", "Kate", "Kathy", "Kyoko", "Lana", "Laura", "Lekha", "Lesya", "Linh",
    "Luciana", "Matilda", "Meijia", "Melina", "Milena", "Moira", "Montse", "Mónica", "Nicky",
    "Noelle", "Nora", "Ona", "Paulina", "Piya", "Samantha", "Sandy", "Sara", "Satu", "Serena",
    "Shelley", "Sinji", "Soumya", "Stephanie", "Susan", "Tara", "Tessa", "Tina", "Tingting",
    "Tünde", "Vani", "Yelda", "Yuna", "Zoe", "Zosia", "Zuzana",
];

/// Parses one `say -v ?` line: `<name>  <locale>  # <sample>`. The name can
/// contain spaces and parentheses (`Bad News`, `Eddy (English (US))`), so the
/// locale is the last token before `#` and the name is everything before it.
fn parse_voice_line(line: &str) -> Option<TtsVoice> {
    let head = line.split('#').next()?.trim_end();
    let (name, locale) = head.rsplit_once(char::is_whitespace)?;
    let name = name.trim();
    if name.is_empty() || locale.is_empty() {
        return None;
    }
    // `Eddy (English (US))` and `Ava (Enhanced)` → `Eddy` / `Ava`.
    let label = name.split(" (").next().unwrap_or(name).to_string();
    let quality_tier = name.contains("(Enhanced)") || name.contains("(Premium)");
    let kind = if NOVELTY.contains(&label.as_str()) {
        "novelty"
    } else if ARTIFICIAL.contains(&label.as_str()) && !quality_tier {
        "artificial"
    } else {
        "lifelike"
    };
    let gender = if kind == "novelty" {
        "U"
    } else if FEMALE.contains(&label.as_str()) {
        "F"
    } else if MALE.contains(&label.as_str()) {
        "M"
    } else {
        "U"
    };
    Some(TtsVoice {
        is_default: name == DEFAULT_VOICE,
        name: name.to_string(),
        label,
        locale: locale.to_string(),
        gender,
        kind,
    })
}

fn parse_voice_list(text: &str) -> Vec<TtsVoice> {
    let mut voices: Vec<TtsVoice> = text.lines().filter_map(parse_voice_line).collect();
    voices.sort_by(|a, b| a.label.cmp(&b.label).then(a.locale.cmp(&b.locale)));
    voices.dedup_by(|a, b| a.name == b.name);
    voices
}

/// Installed macOS voices (`say -v ?`), for the Settings voice picker.
#[tauri::command]
pub fn voice_list_tts_voices() -> Result<Vec<TtsVoice>, String> {
    let output = Command::new("/usr/bin/say")
        .arg("-v")
        .arg("?")
        .output()
        .map_err(|e| format!("failed to list voices: {e}"))?;
    Ok(parse_voice_list(&String::from_utf8_lossy(&output.stdout)))
}

#[cfg(test)]
mod tests {
    use super::*;

    const SAMPLE: &str = "\
Albert              en_US    # Hello! My name is Albert.
Alice               it_IT    # Ciao! Mi chiamo Alice.
Bad News            en_US    # Hello! My name is Bad News.
Eddy (English (UK)) en_GB    # Hello! My name is Eddy.
Eddy (English (US)) en_US    # Hello! My name is Eddy.
Majed               ar_001   # مرحبًا! اسمي ماجد.
Samantha            en_US    # Hello! My name is Samantha.
Ava (Enhanced)      en_US    # Hello! My name is Ava.
";

    fn find<'a>(v: &'a [TtsVoice], name: &str) -> &'a TtsVoice {
        v.iter().find(|x| x.name == name).unwrap_or_else(|| panic!("missing {name}"))
    }

    #[test]
    fn keeps_full_names_with_spaces_and_parens() {
        let v = parse_voice_list(SAMPLE);
        assert_eq!(v.len(), 8);
        assert_eq!(find(&v, "Bad News").label, "Bad News");
        let eddy_us = find(&v, "Eddy (English (US))");
        assert_eq!((eddy_us.label.as_str(), eddy_us.locale.as_str()), ("Eddy", "en_US"));
        assert_eq!(find(&v, "Eddy (English (UK))").locale, "en_GB");
        assert_eq!(find(&v, "Majed").locale, "ar_001");
    }

    #[test]
    fn classifies_gender_and_kind() {
        let v = parse_voice_list(SAMPLE);
        let s = find(&v, "Samantha");
        assert_eq!((s.gender, s.kind, s.is_default), ("F", "lifelike", true));
        let e = find(&v, "Eddy (English (US))");
        assert_eq!((e.gender, e.kind), ("M", "artificial"));
        let a = find(&v, "Albert");
        assert_eq!((a.gender, a.kind), ("M", "artificial"));
        let b = find(&v, "Bad News");
        assert_eq!((b.gender, b.kind), ("U", "novelty"));
        let ava = find(&v, "Ava (Enhanced)");
        assert_eq!((ava.label.as_str(), ava.gender, ava.kind), ("Ava", "F", "lifelike"));
        assert_eq!(find(&v, "Alice").gender, "F");
        assert!(!find(&v, "Alice").is_default);
    }

    /// Live check against this Mac's real `say -v ?` output, then actually
    /// speaks the trickiest names. Run: cargo test --lib -- --ignored --nocapture live_
    #[test]
    #[ignore]
    fn live_voice_list_parses_and_speaks() {
        let v = voice_list_tts_voices().expect("say -v ?");
        let raw_lines = String::from_utf8_lossy(
            &Command::new("/usr/bin/say").arg("-v").arg("?").output().unwrap().stdout,
        )
        .lines()
        .filter(|l| !l.trim().is_empty())
        .count();
        assert_eq!(v.len(), raw_lines, "every installed voice is listed once");
        let defaults: Vec<_> = v.iter().filter(|x| x.is_default).collect();
        assert_eq!(defaults.len(), 1, "exactly one default");
        assert_eq!(defaults[0].name, DEFAULT_VOICE);
        let en: Vec<_> = v.iter().filter(|x| x.locale.starts_with("en")).collect();
        let unknown: Vec<_> = en.iter().filter(|x| x.gender == "U" && x.kind != "novelty").collect();
        println!("{} voices, {} English; English non-novelty with unknown gender: {:?}",
            v.len(), en.len(), unknown.iter().map(|x| &x.name).collect::<Vec<_>>());
        for name in ["Samantha", "Daniel", "Bad News", "Eddy (English (US))", "Grandma (English (UK))"] {
            if v.iter().any(|x| x.name == name) {
                let st = Command::new("/usr/bin/say").arg("-v").arg(name).arg("Rigel voice check.")
                    .status().unwrap();
                println!("spoke with {name:<24} → {st}");
                assert!(st.success(), "say failed for {name}");
            }
        }
    }

    #[test]
    fn skips_blank_and_malformed_lines() {
        assert!(parse_voice_line("").is_none());
        assert!(parse_voice_line("   # nothing").is_none());
    }
}
