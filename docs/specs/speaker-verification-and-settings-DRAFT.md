# DRAFT: speaker verification + settings screen

Status: decisions recorded; mockups v11 (settings) and v12 (enrollment) APPROVED by Tony 2026-11-23. Implementation not started; plan awaiting go-ahead.

## Problem
Rigel hears the TV, room noise and other people. Some of it becomes transcripts that can wake
Rigel or approve actions (2026-11-23: a grunt approved a delete; a TV line almost did).

## Goal
Rigel listens only to Tony's voice, and the settings that control listening and approvals are visible in one place.

## Proposed behaviour (to confirm)
1. Enrollment: Tony records a few short phrases once. The app stores a voice profile locally.
2. Each utterance is compared with the profile. Below a threshold, it is dropped before the wake word or any approval sees it.
3. Destructive approvals still need a click (or a clear spoken yes that also passes the check). A recording of Tony's voice must not be enough on its own.
4. Settings screen (mockup required): wake word on/off, speaker check on/off and its threshold, re-enroll,
   retry count (currently 3 empty listens), approval log location, and the mic input.

## Limits
- Accuracy drops with a cold, a tired voice, or a loud room. Expect some false rejects.
- A similar voice can pass. The check reduces false triggers; it is not a security boundary.
- It does not fix the noise floor: the threshold can sit high for minutes after a loud sound.

## Decisions (Tony, 2026-11-23)
1. Goal: both. Stop false wake-ups AND false approvals. The check also gates approvals.
2. Enrollment: 3 phrases. Store the voice profile in the app database (SQLite), not a file.
3. TV: the app must not hear the TV unless Tony asks it to. The check runs before any transcript is used.
4. Settings: Tony controls all settings. Dangerous settings show a warning next to them.
5. Model: research first (below).

## Research (2026-11-23)
- Candidate: ECAPA-TDNN speaker embeddings (SpeechBrain, Apache-2.0). An ONNX export exists (about 83 MB). It can run from Rust with ONNX Runtime (the `ort` crate). Source: huggingface.co/astrolabos/ecapa-tdnn; the ONNX export is a packaging convenience, not a new model.
- Alternatives: WeSpeaker ResNet34 (256-dim, ONNX, used by polyvoice); a pure-Rust DSP baseline (mel statistics), which is light but weaker.
- Caveat: one benchmark found ECAPA-TDNN accuracy dropped sharply in production audio (channel and codec effects; 29.8% to 51.3% EER). So we must test on Tony's own mic and room, not trust published numbers.
- Plan: pick one model, measure false accept and false reject on Tony's recorded clips (including TV audio), then tune the threshold.

## Not in scope yet
Multi-user support. Speaker identification for other people. Any change to the approval gate's click path.
