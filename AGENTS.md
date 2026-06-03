# terminal-distil — Agent Guide

작은 open model(Qwen 계열)을 terminal/CLI agent로 distill — recovery-training data를 어디서 뽑느냐가 핵심인 연구 프로젝트.

## 📌 Project memory lives in HTML

**The project "memory DB" is in [`MEMORY.html`](./MEMORY.html).**
Before starting a session or following up, **open `MEMORY.html` first** to see current status, risks, and next steps.

- Memory is kept as HTML (not markdown) — easier to read in a browser and structurally clearer.
- When something meaningful changes (experiment result, decision, verification, risk shift), **update `MEMORY.html`**:
  add a line to the **업데이트 로그 (update log)** at the bottom and bump the "마지막 갱신 (last updated)" date in the top banner.
- Supporting evidence: `survey/risks.md` (verified, most trustworthy) and `survey/related-work-survey.md` (deep-research report + Appendix C re-verification log dated 2026-06-03; all cited sources fetch-verified).

The same convention is documented in `CLAUDE.md` for Claude sessions.

## 💬 Discussion threads with Claude

We discuss design decisions in **append-only markdown threads** under `survey/discussion-NNN-<topic>.md` (each has an `.html` mirror that Claude keeps in sync).

**How to participate (Codex):**
- Read the whole thread file first, plus `MEMORY.html` for context.
- **Append only** — never edit or delete others' messages. Add your message at the end as:
  `## <N> — @codex (YYYY-MM-DD)` followed by your body. `<N>` increments by 1.
- Use `@claude` / `@codex` as author tags. Answer the open questions directly; disagree where warranted.
- When you finish writing, stop — Claude watches the file and will respond. Do NOT touch the `.html` mirror (Claude syncs it).
- **Active thread:** `survey/discussion-001-first-experiment.md` — "가설 검증을 위한 첫 실험을 무엇부터 할 것인가".
