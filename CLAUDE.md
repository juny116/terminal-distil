# terminal-distil

작은 open model(Qwen 계열)을 terminal/CLI agent로 distill — recovery-training data를 어디서 뽑느냐가 핵심인 연구 프로젝트.

## 📌 프로젝트 메모리는 HTML입니다

**이 프로젝트의 "메모리 DB"는 [`MEMORY.html`](./MEMORY.html)에 있습니다.**
새 세션을 시작하거나 follow-up 하기 전에 **먼저 `MEMORY.html`을 열어 현재 상태/리스크/다음 할 일을 확인**하세요.

- 마크다운이 아니라 HTML로 관리합니다 (작성자가 브라우저에서 보기 편하고, 구조가 잘 보임).
- 의미 있는 진전(실험 결과, 결정, 검증, 리스크 변동)이 생기면 `MEMORY.html`을 갱신하세요:
  하단 **업데이트 로그**에 한 줄 추가 + 상단 banner의 "마지막 갱신" 날짜 수정.
- 상세 근거는 `survey/risks.md`(검증 완료판, 가장 신뢰 가능)와 `survey/related-work-survey.md`(deep-research 본 리포트 + 2026-06-03 재검증 로그 Appendix C; 모든 인용 출처 fetch 검증 완료)에 있습니다.

> Codex 등 다른 에이전트도 동일 규약을 따르도록 `AGENTS.md`에도 같은 안내가 있습니다.

## 💬 Codex와의 논의 스레드

설계 결정은 **append-only 마크다운 스레드** `survey/discussion-NNN-<topic>.md`에서 한다 (각 `.html` 미러는 Claude가 동기화).
- 메시지 = `## <N> — @author (YYYY-MM-DD)` (append-only, 남의 메시지 수정 금지). author는 `@claude`/`@codex`.
- `.md`를 갱신할 때마다 같은 폴더의 `.html` 미러도 동기화. 합의된 결론은 `MEMORY.html`에 반영.
- **활성 스레드**: `survey/discussion-004-core-experiment.md` (핵심 실험: TermiGen vs DAgger vs Ours). 과거: #001~#003.
- **이 프로젝트 전용 Codex = tmux 세션 `terminal-codex`** (cwd=이 repo, gpt-5.5). 핑은 `tmux send-keys -t terminal-codex '<msg>'` 후 별도 `tmux send-keys -t terminal-codex Enter`로 제출. ⚠️ **메시지를 `/`나 경로(`survey/...`)로 시작하지 말 것** — Codex TUI가 슬래시 명령으로 오해함. 앞에 단어 하나(예: "작업 요청:" / "스레드 ...")를 붙여라. ⚠️ **제출이 안 먹으면(메시지가 입력창에 남아있으면) `C-c` 금지(codex가 꺼짐!) — 그냥 `tmux send-keys -t terminal-codex Enter`를 한 번 더 쳐라.** (juny116 확인: 보통 Enter 문제다.) 세션이 없거나 codex가 꺼졌으면 재생성: `tmux send-keys -t terminal-codex 'codex' Enter` (업데이트 프롬프트 뜨면 `2`+Enter로 skip, 최초 trust 프롬프트는 Enter로 승인). codex 재시작 시 이전 대화 맥락은 날아가니, 핑에 **읽을 파일 경로를 명시**(append-only md라 codex가 읽고 이어감). 다른 tmux의 `codex`/`omni-codex` 세션은 **다른 프로젝트용이니 핑 금지.**
