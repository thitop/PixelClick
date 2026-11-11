# Per-image "delay before click" — design

Status: awaiting approval. Size: small change (short design).

## Intent
After a target image is detected, wait a set time before clicking it (e.g. let a
button finish animating). Each image has its own wait. Today the app clicks the
moment it sees the target.

## Goals
- Every image in the list has its own "before click" delay, editable in place.
- The wait is interruptible: Stop and Pause take effect immediately.
- After the wait the screen is checked again, so the click lands on the
  target's current position, or is skipped if the target is gone.

## Non-goals
- No random jitter, no global default slider, no click-count limits.
- Color mode is unchanged (it still clicks immediately; no per-target list there).

## Approaches considered
- A. One global delay: simple, but cannot express "image 1 now, image 2 after 0.5 s".
- **B. Per-image delay only (chosen by the user).**
- C. Global default + per-image override: most flexible, more UI; not chosen.

## Design (my calls marked *)
- **Data:** each template is `{path, pre_delay_ms}`, range 0–10 000 ms, 0.05 s steps.
  New images start at 0 (current behaviour).*
- **Old `delay` field:** it held the "wait between clicks" slider value captured at
  add time and was used as a per-image cooldown. It is retired: the global
  "Wait between clicks" slider alone controls cooldown. Saved configs' old values
  are ignored on load so nobody suddenly gets a 0.3 s pre-click wait.*
- **UI:** each row in "What to click" shows `1  name.png   [ 0.00 ] s   ×`.
  The field commits on Enter or focus-out; invalid or out-of-range input reverts.*
- **Worker flow** (template mode): found → if the click cooldown allows → if
  `pre_delay > 0`, wait in 20 ms steps (abort on Stop/Pause) → capture again and
  re-detect → found: click the new position, advance the sequence; not found:
  no click, no advance, keep scanning. `pre_delay == 0` clicks immediately.
- **Status:** the stats strip's Target shows "Waiting" during the delay.*
- **Tests:** detector returns each image's delay; worker waits, re-checks, skips
  when the target vanished, aborts the wait on stop; config migration ignores old values.

## Left to the builder
Exact widget sizing of the in-row field; log wording.
