//! Text-to-speech via macOS's built-in `say`, shaped by an ffmpeg "warm"
//! filter when ffmpeg is installed (plain `say` otherwise). No network —
//! matches the "local execution engine" ethos.

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
    let mut cmd = speak_command(&text, &voice, find_ffmpeg());

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

/// Speaking rate (words per minute) for Rigel's voice: a touch quicker than
/// `say`'s default so replies sound conversational rather than read out.
pub const SPEAK_RATE: &str = "178";

/// Rigel's "warm" voice treatment (chosen by ear from the mockups in
/// docs/mockups/voice/, sample h2-warm): trims rumble, adds body around
/// 200 Hz, softens the tinny 3.5 kHz and 7 kHz bands that make `say` sound
/// synthetic, adds a very faint room, and gently evens out loudness. Every
/// stage stays inside the 80 Hz–9 kHz speech band.
pub const WARM_FILTER: &str = "highpass=f=80,\
equalizer=f=200:t=q:w=1:g=3,\
equalizer=f=3500:t=q:w=1.5:g=-3,\
equalizer=f=7000:t=q:w=1:g=-4,\
lowpass=f=9000,\
aecho=0.9:0.3:18|31:0.07|0.05,\
acompressor=threshold=0.2:ratio=2:attack=10:release=150,\
volume=1.4";

/// ffmpeg isn't part of macOS, and a GUI app's PATH doesn't include Homebrew,
/// so look in the usual install locations directly.
fn find_ffmpeg() -> Option<&'static str> {
    ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
        .into_iter()
        .find(|p| std::path::Path::new(p).exists())
}

/// Builds the process that speaks `text`. With ffmpeg available: `say`
/// renders to a temp file, ffmpeg applies WARM_FILTER, and the shell then
/// `exec`s afplay, so the spawned child *is* the player and killing it stops
/// the audio. Without ffmpeg: plain `say`, exactly as before. Text, voice
/// and paths travel as positional arguments, never spliced into the script.
fn speak_command(text: &str, voice: &str, ffmpeg: Option<&str>) -> Command {
    let Some(ffmpeg) = ffmpeg else {
        let mut cmd = Command::new("/usr/bin/say");
        cmd.arg("-v").arg(voice).arg("-r").arg(SPEAK_RATE).arg(text);
        return cmd;
    };
    static SEQ: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    let n = SEQ.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let dir = std::env::temp_dir();
    let stem = format!("rigel-tts-{}-{n}", std::process::id());
    let raw = dir.join(format!("{stem}.aiff"));
    let out = dir.join(format!("{stem}.wav"));
    // $1 text, $2 voice, $3 rate, $4 raw, $5 out, $6 ffmpeg, $7 filter, $8 tmp dir.
    // Clears earlier utterances' leftovers first (the previous player has
    // already been killed by stop_current), and falls back to plain `say` if
    // rendering fails so Rigel is never silent.
    let script = r#"find "$8" -maxdepth 1 -name 'rigel-tts-*' ! -name "$(basename "$4")" ! -name "$(basename "$5")" -delete 2>/dev/null
/usr/bin/say -v "$2" -r "$3" -o "$4" -- "$1" \
  && "$6" -y -loglevel error -i "$4" -af "$7" "$5" \
  && rm -f "$4" && exec /usr/bin/afplay "$5"
rm -f "$4" "$5"
exec /usr/bin/say -v "$2" -r "$3" -- "$1""#;
    let mut cmd = Command::new("/bin/sh");
    cmd.arg("-c").arg(script).arg("sh")
        .arg(text).arg(voice).arg(SPEAK_RATE)
        .arg(&raw).arg(&out).arg(ffmpeg).arg(WARM_FILTER).arg(&dir);
    cmd
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

    fn args(cmd: &Command) -> Vec<String> {
        cmd.get_args().map(|a| a.to_string_lossy().into_owned()).collect()
    }

    #[test]
    fn plain_say_when_no_ffmpeg() {
        let cmd = speak_command("Hi Tony", "Samantha", None);
        assert_eq!(cmd.get_program(), "/usr/bin/say");
        assert_eq!(args(&cmd), ["-v", "Samantha", "-r", SPEAK_RATE, "Hi Tony"]);
    }

    #[test]
    fn warm_chain_passes_text_as_an_argument_not_script() {
        let nasty = "it's \"$(rm -rf ~)\"; done";
        let cmd = speak_command(nasty, "Samantha", Some("/opt/homebrew/bin/ffmpeg"));
        assert_eq!(cmd.get_program(), "/bin/sh");
        let a = args(&cmd);
        assert!(!a[1].contains(nasty), "text must not be spliced into the script");
        assert_eq!(&a[3..6], [nasty, "Samantha", SPEAK_RATE]);
        assert!(a[6].ends_with(".aiff") && a[7].ends_with(".wav"));
        assert_eq!(a[9], WARM_FILTER);
        assert!(a[1].contains("exec /usr/bin/afplay"), "player must replace the shell");
    }

    #[test]
    fn warm_filter_stays_in_speech_band() {
        assert!(WARM_FILTER.starts_with("highpass=f=80,"));
        assert!(WARM_FILTER.contains("lowpass=f=9000"));
        assert!(!WARM_FILTER.contains(' '), "ffmpeg -af takes one unbroken chain");
    }

    /// Speaks through the real warm chain on this Mac. Listen for it.
    /// Run: cargo test --lib -- --ignored --nocapture live_warm
    #[test]
    #[ignore]
    fn live_warm_chain_speaks() {
        let ff = find_ffmpeg().expect("ffmpeg installed");
        let st = speak_command("Hello, Tony. This is Rigel's warm voice.", DEFAULT_VOICE, Some(ff))
            .status().unwrap();
        assert!(st.success());
    }

    /// Interrupting a warm reply must stop the audio: the killed child has to
    /// be afplay itself, not a shell that leaves the player running.
    /// Run: cargo test --lib -- --ignored --nocapture live_warm_interrupt
    #[test]
    #[ignore]
    fn live_warm_interrupt_stops_audio() {
        let ff = find_ffmpeg().expect("ffmpeg installed");
        let mut child = speak_command(
            "This is a long sentence that should be cut off partway through, well before it finishes.",
            DEFAULT_VOICE, Some(ff)).spawn().unwrap();
        std::thread::sleep(Duration::from_millis(2500));
        let pid = child.id().to_string();
        child.kill().unwrap();
        child.wait().unwrap();
        std::thread::sleep(Duration::from_millis(300));
        let left = Command::new("/bin/ps").args(["-p", &pid]).output().unwrap();
        assert!(!String::from_utf8_lossy(&left.stdout).contains(&pid), "player still alive");
        let players = Command::new("/usr/bin/pgrep").arg("afplay").output().unwrap();
        assert!(players.stdout.is_empty(), "orphaned afplay still playing");
    }

    #[test]
    fn skips_blank_and_malformed_lines() {
        assert!(parse_voice_line("").is_none());
        assert!(parse_voice_line("   # nothing").is_none());
    }
}
