# Start here: Pi 4 offline maintenance demo

This repository has working PC-trained snapshot classifiers and a local replay dashboard.
The next deployment target is **Raspberry Pi 4 / 8 GB / ARM64**. Never report Pi acceptance
or a successful real LLM run without evidence from that device.

## Read in this order

1. `docs/PROJECT_STATUS.md` — what is done, limitations and the next work.
2. `docs/PI_HANDOFF.md` — exact PC packaging / Pi installation / offline acceptance steps.
3. `docs/DEMO_RUNBOOK.md` — presenter script and expected screen behavior.
4. `docs/ARCHITECTURE.md` — classifier / Python bridge / LLM / dashboard contracts.
5. `docs/PI_SCREEN_DESIGN.md` — 800×480 UI, persisted history and bounded data questions.

## Immediate next action

- On a **fresh Git clone / Pi**: the repository now includes `runtime/` (primary model,
  curated replay, parity, locked requirements and hashes), both AI4I artifacts, original
  pump artifacts, public datasets and `wheels/pi4-cp312/`. Read `docs/PI_HANDOFF.md`
  section 0. Install Python 3.12, create a venv, install `requirements-pi.txt` from the
  bundled ARM64 wheels, then run `python pi_check.py` and `python dashboard.py`.
  No training or separate model download is required for the template demo.
- On **PC with existing artifacts**: run tests, then `python prepare_pi.py --out pi-release-NAME`.
  Use the repository venv, not an arbitrary system interpreter. A ZIP is optional for USB transfer.
- On **Pi with a release**: verify archive hash from the PC, extract, install the exact release
  runtime, then `python pi_check.py --release .` and `python dashboard.py --release .`.
- If required tracked runtime files are missing, check the clone and `docs/GIT_CONTENTS.md`.
  Do not silently train on Pi,
  invent a model, change thresholds or substitute another split to make the screen look good.
- No Pi is connected in the preparation workspace. Hardware work remains pending.

## Implementation map

| Area | Entry point |
| --- | --- |
| Classifier training | `ai4i.py`, `pump.py`, `experiments.py` |
| Shared AI4I deterministic facts text | `ai4i.summary_text` |
| Orchestration / schema / facts / summary | `bridge.InferenceBridge` |
| Guarded local LLM subprocess + fallback | `pump.summarize` |
| HTTP + single-worker CSV replay state | `dashboard.py` |
| SQLite evidence + whitelisted question intents | `data_assistant.py` |
| Browser UI, no CDN or external fonts | `web/` |
| Immutable transfer bundle + checksums | `prepare_pi.py` |
| Parity, runtime checks, benchmark evidence | `pi_check.py` |
| Optional boot service template | `deploy/pump-dashboard.service` |

## Constraints and verification

- Default demo is **AI4I ordered_primary**. AI4I is synthetic manufacturing data, not a real pump.
  Original pump results remain near baseline. Keep these warnings visible.
- This is CSV replay, not live sensors or RUL prediction. The data question page is bounded
  retrieval/aggregation with citations, not an open diagnostic chatbot.
- Classifier alone sets `status` using the stored threshold. LLM cannot alter status or numbers.
  It chooses A/B; invalid, inconsistent, missing or timed-out output falls back to template.
  Optional `--llm-questions` separately routes questions to a fixed intent enum; Python alone
  runs fixed SQL and computes answers. Do not allow LLM-generated SQL or machine facts.
- Dashboard targets an 800×480 full-screen viewport: overview, history and questions are separate
  pages. Keep source warnings visible. Do not put all diagnostic panels back on the home screen.
- Store snapshots in local `evidence/telemetry.sqlite3` (override with `--database`). Reset/restart
  creates a new session without deleting records. Do not commit actual machine telemetry.
- Keep `measured_at` separate from replay recording time. AI4I has no real machine IDs or
  measurement timestamps: never use product IDs or replay time to answer "which machine today".
- Never derive an input from `Maintenance_Flag`, `Machine failure`, failure-mode labels or IDs.
- Runtime makes no downloads/cloud calls. Provision Python, ARM64 wheels, llama.cpp and GGUF
  while online. Do not copy a Windows venv or Windows wheels to ARM64.
- Load only trusted `.joblib` files. Manifest hashes check transfer integrity, not publisher identity.
- One backend worker and shared replay session per server; LLM subprocesses never overlap.
  Pause stops future rows; a current LLM call may finish for up to 30 seconds.
  Questions require replay to be paused and the current row finished; question routing has a
  10-second timeout. LLM success mocks remain separate from real GGUF acceptance.
- Tests: `.venv/Scripts/python -m unittest -v` (Windows) / `.venv/bin/python -m unittest -v` (Pi).
  New runtime changes must verify real model → API → browser, plus fallback with mocks.
  Mock LLM success does not count as an actual GGUF test.
- Record target results under ignored `evidence/`. Summarize actual findings in
  `docs/PROJECT_STATUS.md`. The user's publication request authorizes the two public datasets,
  approved model bundles and ARM64 wheels already in Git. Keep their attribution/licensing.
  Keep GGUF, venvs, credentials, unrelated external ZIPs and generated release directories ignored.
- Keep `hardware_acceptance_verified=false` until a human reviews target evidence.

## Definition of next milestone

Pi: ARM64, parity passes, template demo completes with internet disconnected, both normal
and alert snapshots visible, classifier <1 s/row, summary <=30 s, system RAM <6 GiB,
thermal/throttling inspected, JSON evidence saved. Optional LLM milestone additionally
requires `local_llm_validated` from a real GGUF and a demonstrated fallback.
