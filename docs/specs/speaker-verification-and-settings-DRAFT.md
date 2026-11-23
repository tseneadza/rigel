# DRAFT: speaker verification + settings screen

Status: draft for discussion. Not approved. No code yet. Mockups first (Tony's rule).

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

## Open questions for Tony
1. Is the goal to stop false wake-ups, to stop false approvals, or both? (Affects the threshold and whether the check gates approvals too.)
2. Enrollment: how many phrases, and how often to re-enroll? Is it okay to store a voice profile on the Mac?
3. Should the speaker check block the TV entirely, or only when Tony is not talking over it?
4. Which settings should Tony change himself, and which should stay fixed for safety?
5. Model choice: an on-device speaker-embedding model. Do you have a preference, or should I research options first?

## Not in scope yet
Multi-user support. Speaker identification for other people. Any change to the approval gate's click path.
