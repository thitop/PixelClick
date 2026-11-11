# Per-image "delay before click" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each target image gets its own editable "before click" wait; after the wait the screen is re-checked and the click lands on the target's current position (or is skipped if it is gone).

**Architecture:** The template dict gains `pre_delay_ms` (replacing the old, misused `delay`). `MultiTemplateDetector` reports it on each `DetectionResult`; `DetectionWorker` does the interruptible wait + re-detect before clicking. The settings list shows an editable seconds field per row that mutates the same dict objects the detector reads, so edits apply live.

**Tech Stack:** Python 3.11+, CustomTkinter, OpenCV, pytest (venv with `requirements-dev.txt`).

**Spec:** `docs/superpowers/specs/2026-11-11-pre-click-delay-design.md`

## Global Constraints

- Range 0–10 000 ms, 0.05 s steps. New images start at 0 (click immediately, current behaviour).
- Old saved `delay` values are ignored on load; only `pre_delay_ms` is read.
- The global "Wait between clicks" slider alone controls cooldown; the per-image cooldown override is retired.
- Wait runs in 20 ms steps and aborts on Stop or Pause with no click.
- After the wait: re-detect; found → click the new position and advance the sequence; not found → no click, no advance.
- Stats strip Target shows "Waiting" during the wait.
- Color mode unchanged (clicks immediately). No random jitter, no click limits.
- The project is not a git repository, so there are no commit steps; run the full test suite at the end of each task instead.

## Review Focus

- Target disappears during the wait: no click, sequence does not advance (Task 2).
- Stop pressed mid-wait: `_step` returns promptly (< 0.5 s for a 5 s delay) and does not click (Task 2).
- Pause pressed mid-wait: wait aborts, no click (Task 2).
- First image fails to load, second has a delay: delay still belongs to the second image, and editing the dict later changes it live (Task 1).
- Typing "abc", "-1" or "11" in a row's field reverts to the previous value; "0.12" snaps to 0.10 (Task 3).

---

### Task 1: Data model and detector

**Files:**
- Modify: `detection/base_detector.py` (`DetectionResult`), `detection/multi_template.py`, `utils/config.py`
- Test: `tests/test_core.py` (update `test_sequential_advances_only_on_advance`), `tests/test_pre_delay.py` (create)

**Interfaces:**
- Produces: `DetectionResult.pre_click_delay_ms: int = 0` (replaces `action_delay_ms`); template dict shape `{"path": Path, "pre_delay_ms": int}`; `utils.config.PRE_DELAY_MAX_MS = 10_000`; `utils.config.normalize_template(entry: dict) -> dict` returning `{"path": Path(entry["path"]), "pre_delay_ms": int}` clamped to `0..PRE_DELAY_MAX_MS`, defaulting to 0 and ignoring any `delay` key.
- `MultiTemplateDetector` keeps the same constructor `(templates: list[dict], threshold, mode)` and reads `entry["pre_delay_ms"]` at `find_target` time (not at construction), so mutating the dict later takes effect.

- [ ] **Step 1: Write failing tests** in `tests/test_pre_delay.py`:
  - `test_normalize_ignores_legacy_delay`: `normalize_template({"path": "a.png", "delay": 300})["pre_delay_ms"] == 0`.
  - `test_normalize_clamps`: `pre_delay_ms` 99999 → 10000; -5 → 0.
  - `test_detector_reports_pre_delay_per_image`: two templates (delays 0 and 700) → `find_target` result for each carries `pre_click_delay_ms` 0 / 700 (use the `scene`-style fixtures from `tests/test_core.py`).
  - `test_failed_load_does_not_shift_delays`: templates `[missing-file, good]` with good's `pre_delay_ms` 700 → result 700; then set `templates[1]["pre_delay_ms"] = 200` and the next `find_target` reports 200.
  Update `test_sequential_advances_only_on_advance` to use `"pre_delay_ms"` and `pre_click_delay_ms`.
- [ ] **Step 2: Run** `pytest tests -q` → new tests FAIL (names undefined).
- [ ] **Step 3: Implement** the rename in `DetectionResult`, `normalize_template` + `PRE_DELAY_MAX_MS` in `utils/config.py`, and in `multi_template.py` store each detector with a reference to its source dict (`list[tuple[TemplateMatchDetector, dict]]`), setting `res.pre_click_delay_ms = int(entry.get("pre_delay_ms", 0))`.
- [ ] **Step 4: Run** `pytest tests -q` → all PASS.

### Task 2: Worker wait and re-check

**Files:**
- Modify: `detection_worker.py` (`_run`, `_push_update`)
- Test: `tests/test_pre_delay.py` (add worker tests; use fakes: capture returning `np.zeros((50, 50, 3), np.uint8)`, a click controller with `ready()`, `move_and_click(x, y)`, `click_count`, `enable()`, `disable()`, `reset_counter()`, and a scripted detector with `find_target`, `is_ready`, `advance`)

**Interfaces:**
- Consumes: `DetectionResult.pre_click_delay_ms` (Task 1); `ClickController.ready(override_delay_ms=None) -> bool`.
- Produces: `DetectionWorker._step(self) -> None` (one full capture→detect→[wait→re-detect]→click→push iteration; `_run` just loops it and handles FPS/sleep); `DetectionWorker._wait_interruptible(self, seconds: float) -> bool` (True if the full wait elapsed, False if `_running` became False or `_paused` became True); `_push_update(self, result, waiting: bool = False)` adds `"waiting": bool` to the status dict.

- [ ] **Step 1: Write failing tests** (set `worker._running = True`, `worker._detector = fake`, `worker._auto_click = True`):
  - `test_zero_delay_clicks_immediately_without_recapture`: one scripted found result, delay 0 → one click, capture called once.
  - `test_delay_then_clicks_new_position`: delay 100 ms, first result at (10, 10), re-detect returns (20, 25) → one click at (20, 25), `advance` called once.
  - `test_target_vanishes_during_wait`: re-detect returns not found → zero clicks, `advance` not called.
  - `test_stop_during_wait_aborts`: delay 5000 ms; run `_step` in a thread, set `worker._running = False` after 100 ms; thread ends within 0.5 s and zero clicks.
  - `test_pause_during_wait_aborts`: same with `worker._paused = True`.
  - `test_cooldown_blocks_wait`: `ready()` returns False → no wait, no click.
- [ ] **Step 2: Run** `pytest tests/test_pre_delay.py -q` → FAIL (`_step` missing).
- [ ] **Step 3: Implement** `_step` and `_wait_interruptible` as specified above: skip everything if `not self._click.ready()`; if `pre_click_delay_ms > 0` push a `waiting=True` status, wait in 20 ms steps, capture and detect again, annotate `_last_frame`, and bail without clicking when not found; click via `move_and_click(abs_x, abs_y)` with no delay override (absolute position = result + region offset, as today); call `detector.advance()` only if the click happened. Refactor `_run` to call `_step()` inside its existing try/except.
- [ ] **Step 4: Run** `pytest tests -q` → all PASS.

### Task 3: UI field, wiring, persistence

**Files:**
- Modify: `gui/settings_frame.py`, `gui/main_window.py`
- Test: `tests/test_pre_delay.py` (add `parse_pre_delay` tests)

**Interfaces:**
- Consumes: template dict `{"path", "pre_delay_ms"}`, `normalize_template` (Task 1); status key `"waiting"` (Task 2).
- Produces: module-level `gui.settings_frame.parse_pre_delay(text: str) -> float | None` (seconds snapped to 0.05 and rounded to 2 decimals; `None` when not a number or outside 0–10); `SettingsFrame(..., on_template_delay_change=Callable[[int, float], None])` called with `(row_index, seconds)` when a row's field commits (Enter or focus-out, valid input only; invalid input restores the previous text); `MainWindow._on_template_delay(self, index: int, seconds: float) -> None` writes `self._templates[index]["pre_delay_ms"] = int(round(seconds * 1000))`.

- [ ] **Step 1: Write failing tests**: `parse_pre_delay("0.3") == 0.3`; `"0.12"` → 0.1; `"0"` → 0.0; `"10"` → 10.0; `"abc"`, `"-1"`, `"11"`, `""` → `None`. (Importing `gui.settings_frame` pulls in customtkinter and icon deps; the dev venv already has them.)
- [ ] **Step 2: Run** `pytest tests/test_pre_delay.py -q` → FAIL.
- [ ] **Step 3: Implement** `parse_pre_delay`; in `set_template_list` replace the delay-less row with `index, name, [CTkEntry width 56 showing f"{pre_delay_ms/1000:.2f}"], "s", ×`, bound to `<Return>` and `<FocusOut>`; in `main_window.py` add `_on_template_delay`, create templates with `{"path": p, "pre_delay_ms": 0}` in `_add_template`, load with `normalize_template` in `_restore_state` (still skipping missing files), save `{"path": str(path), "pre_delay_ms": ...}` in `_save_config_state`, and in `_apply_status` show `Target = "Waiting"` (color `T.WARN`) when `status.get("waiting")`. Add the hint "Minimum time between two clicks." under the "Wait between clicks" slider in Step ③ (it currently has none), so it is not confused with the per-image delay.
- [ ] **Step 4: Run** `pytest tests -q` → all PASS; then launch the app once (`python main.py`), add two images, set 0.50 on one, confirm the field commits and the Target stat shows "Waiting" in a run.
