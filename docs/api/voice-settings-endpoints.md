# API Endpoint: Voice Settings

## Overview
Two endpoints backing the Settings window's Voice tab. They store
**preferences only** — the wake-word reference and speech model live on
disk under `~/.rigel/` and are managed by the native app, not the sidecar.
Follows the same pattern as `orb-config` and `llm-config`
(one JSON value in the `settings` table).

---

## `GET /api/rigel/settings/voice-config`

Returns the persisted voice preferences, or defaults if never saved.

### Response (200)
```json
{
  "tts_voice": null,
  "speak_typed_replies": false,
  "enabled": false
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `tts_voice` | string \| null | macOS voice name from `say -v ?` (e.g. `"Samantha"`); `null` = system default. |
| `speak_typed_replies` | boolean | Speak replies to typed messages too (voice-initiated replies are always spoken). |
| `enabled` | boolean | Start always-on wake-word listening at launch. The desktop app also applies this immediately when toggled. |

---

## `POST /api/rigel/settings/voice-config`

Saves the preferences. The full object is required (pydantic
`VoiceConfig`; missing fields take the defaults above).

### Request Body
```json
{ "tts_voice": "Samantha", "speak_typed_replies": true, "enabled": true }
```

### Response (200)
```json
{ "ok": true }
```

### Errors
- `422` — a field has the wrong type (e.g. `"enabled": "yes"`).

---

## Client
`desktop/src/api.js`: `getVoiceConfig()`, `saveVoiceConfig(config)`.
The Settings tab persists `enabled` immediately when the checkbox is
toggled (so the listener state and the saved config can't disagree) and
the rest on **Save**.

## Related
- [`docs/features/voice-pipeline.md`](../features/voice-pipeline.md)
- Native commands (not HTTP) that do the actual work: `voice_speak`,
  `voice_stop_speaking`, `voice_list_tts_voices`, `voice_enroll_wakeword`,
  `voice_wakeword_status`, `voice_clear_wakeword`, `voice_stt_model_status`,
  `voice_download_stt_model`, `voice_set_enabled`, `voice_is_enabled` —
  wrapped in `desktop/src/voice.js`.
