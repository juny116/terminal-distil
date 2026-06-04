# 연구 리스크 정리 — 검증 완료판 (for 자체검토 + 외부 리뷰)

> **이 문서의 목적**: 우리 연구 방향의 risk를, *직접 fetch해서 검증한 근거*와 함께 쉽게 정리. 작성자(juny116)와 외부 리뷰어(Codex)가 같이 pressure-test 하기 위함.

---

## 0. 30초 컨텍스트 (리뷰어용)

- **프로젝트**: 작은 open model(Qwen 계열)을 **terminal/CLI agent**로 distill. 학습 데이터는 trajectory SFT.
- **Thesis (검토 대상)**: *"Recovery-training data는 teacher가 만든/주입한 failure가 아니라, **실제 target student를 rollout해서 걔가 진짜로 깨지는 지점(on-policy failure distribution)** 에 맞춰야 한다. Agent failure는 distributional하므로 recovery supervision은 idealized teacher가 아니라 deployed student에 align되어야 한다."*
- **현재 repo 상태**: `gpt_agent.py`가 **teacher(GPT-5.4)에 ε=0.2 Bernoulli error injection + Generator-Critic**으로 trajectory 수집 → `data/sft_all.jsonl` ≈ 2,302개. 즉 **지금 가진 데이터는 우리가 "안 좋다"고 비판하려는 바로 그 teacher-injected 방식**. student rollout 기반 failure mining(파이프라인 step 3–4)은 **아직 미구현**.
- **제안하는 방법 (검토 핵심 — teacher가 복구를 *시연*하는 게 아님!)**: ① 실제 student를 rollout해서 *걔가 진짜 깨지는* on-policy 실패 상태를 수집 → ② **teacher는 복구 경로를 만들지 않고, 그 실패를 보고 *힌트만* 생성** → ③ student가 그 힌트를 참고해 **자기가 복구를 재시도** → ④ **성공한 student 자신의 복구 경로**를 SFT. 즉 *"선생은 콕 찔러주고, 답은 학생이 자기 손으로 쓴다"* (STaR/rationalization 계열). hint-free vs hint-based로 "복구를 내재화했나 vs 힌트만 읽나"를 검사하려 함.
- **핵심 질문**: 이 방향이 (1) novel한가, (2) 진짜 효과가 있나, (3) 누가 이미 했나(scoop).

---

## 1. 검증 스코어카드 (전부 직접 fetch함, 2026-06)

| 논문 | arXiv | 실재? | 핵심주장 정확? | 도메인 | 비고 |
|---|---|---|---|---|---|
| **TermiGen** | 2602.07274 | ✅ 진짜 | ✅ **verbatim 확인** | **Terminal** | 우리 motivation을 abstract에서 선점. 해결책은 teacher-injection |
| **Wu et al.** "Synthetic Error Injection Fails…" | 2512.02389 | ✅ 진짜 | ✅ **수치까지 일치** | toy reasoning | 1~1.5B 모델 + 4자리곱셈/4×4스도쿠. agent 아님 |
| **Revisiting DAgger in the Era of LLM-Agents** | 2605.12913 | ✅ 진짜 | ✅ | **SWE** (≠terminal) | student↔teacher turn mix, covariate shift |
| **OEC** (On-policy Expert Corrections) | 2512.14895 | ✅ 진짜 | ✅ (사소오류¹) | **SWE** (≠terminal) | student rollout 후 expert가 이어받아 correction |
| **AgentDebug** "Where LLM Agents Fail…" | 2509.25370 | ✅ 진짜 | ✅ | ALFWorld/GAIA/WebShop | self-failure taxonomy + 진단 + re-rollout |

¹ OEC 모델 사이즈는 우리 deep-research 리포트가 "4B/8B"라 했으나 **실제로는 7B/32B** (SWE-bench Verified, +14%/+13% relative). 리포트의 사소한 오류 — 정정.

**결론: 5개 전부 실존하고, deep-research 리포트의 성격 규정은 substantially 정확.** (워크플로우가 ID를 지어낸 게 아님.)

핵심 verbatim 근거 2개:
- **TermiGen abstract**: *"standard instruction tuning uses expert trajectories that rarely exhibit simple mistakes common to smaller models. This creates a **distributional mismatch**, leaving student models ill-equipped to recover from their own runtime failures."* → **우리가 내세우려던 문제의식 그대로.**
- **Wu et al. 본문 수치**: Qwen2.5/Sudoku error recognition **94%→8%**, Qwen2.5/곱셈 correction **99%→40%**, Gemma-3/곱셈 recognition **83%→20%**, 교정 실패 케이스의 **25%는 원래 실수를 그대로 반복(parrot)**. 결론: *"on-policy RL methods have proven uniquely effective."*

---

## 2. 리스크 (치명도 순)

### 🟠 R1 — "on-policy *data* ≠ on-policy *training*" (제안 방법으로 *상당 부분 선제 방어됨* — 정정)

> ⚠️ **정정**: 이 문서 초판은 R1을 🔴로 두고 "teacher가 복구를 시연해 SFT"라 가정했으나, **실제 방법은 teacher가 힌트만 주고 student가 자기 복구를 생성**한다(§0 제안 방법). 그래서 이 리스크는 크게 약해진다.

- **쉬운 말로**: 모방하는 복구 토큰이 **teacher 게 아니라 student 자신의 것**(힌트로 유도만 됨) → on-distribution, covariate shift가 작다. **STaR(2022)** 통찰 그대로.
- **왜 *덜* 위협**: Wu et al.이 때린 건 *injected 오류 + (teacher)교정 SFT*다. 우리 방법은 **실패 출처도 student, 복구도 student**라 Wu의 셀과 가로·세로 둘 다 다름. 게다가 **학습 실패분포 = 테스트 실패분포 = 같은 student의 on-policy 실패**라 Wu가 지적한 mismatch를 *직접 메운다*.
- **남는 잔여 위협**: 그래도 결국 *고정 데이터셋 SFT*라, Wu의 더 깊은 메시지("분포 맞춰도 SFT < RL")가 마진에서 물 수 있음.
- **검증**: ✅ Wu et al. 실재 + 결론 + 수치 확인. 단 **1.5B + toy task**라 terminal 전이는 미검증.
- **죽냐/사냐**: ablation에서 `student-mined hint-guided self-recovery SFT`가 `injected-SFT`를 **유의하게 못 이기거나**, `student-mined+RL` ceiling이 압도적이면 → RL 쪽 재구성 검토. (RL arm은 *이기려고*가 아니라 *gap 재려고* 둔다.)

### 🟠 R2 — TermiGen이 *문제의식*을 이미 선점

- **쉬운 말로**: "expert trajectory엔 small model 실수가 없어서 student가 자기 실패를 복구 못한다"는 우리 핵심 motivation을 **TermiGen이 abstract에 이미 박아놨다.**
- **검증**: ✅ **verbatim 확인** (위 인용). TermiGen은 같은 terminal 도메인 + 같은 문제 정의.
- **살아있는 wedge**: TermiGen의 *해결책*은 **teacher-side Generator-Critic injection** (target student를 rollout 안 함). → 우리는 **"문제 발견"이 아니라 "해결책(student-mined)"에서만** 차별화 가능.
- **죽냐/사냐**: framing으로 우회 가능(아래 §3). 단 "우리가 mismatch를 발견했다" 톤으로 쓰면 즉시 reject감.

### 🟠 R3 — 실증 핵심 주장이 이미 published (scoop)

- **쉬운 말로**: "injected failure ≠ on-policy failure, 그리고 injected로 학습하면 실패한다"는 우리 thesis의 *실증적 알맹이*를 **Wu et al.이 이미 controlled experiment로 증명.**
- **검증**: ✅ 확인. **단 결정적 한계**: 그건 **1~1.5B 모델 + toy task(곱셈/스도쿠)**. **agentic / terminal multi-step tool-use에서는 아무도 안 봄.** ← 여기가 우리 빈칸.
- **죽냐/사냐**: "우리가 발견"이 아니라 **"Wu et al.을 terminal agent로 확장 실측 + TermiGen 비판 근거로 재배치"** 로 가면 살아남음.

### 🟡 R4 — Method 레시피도 SWE에선 이미 작동함 (DAgger-LLM, OEC)

- **쉬운 말로**: "student rollout → 실패 지점에서 expert correction"이라는 **레시피 자체는 SWE-bench에서 이미 됨** (2605.12913, 2512.14895). 우리가 "방법이 새롭다"고 하면 약함.
- **검증**: ✅ 둘 다 실재, **SWE 도메인** 확인 (terminal 아님). 둘 다 covariate shift를 명시적으로 공격.
- **살아있는 wedge**: **terminal 도메인 + recovery-data 산출물(dataset)** 은 아무도 안 함. 단 정직하게 cite해야.
- **주의**: 이 둘은 DAgger식이라 **R1과 같은 한계(label은 여전히 expert=off-policy)** 를 공유 → 우리가 RL로 안 가면 차별점이 "도메인뿐"이 될 위험.

### 🟡 R5 — "분포 매칭"의 한계효용이 작을 수 있음 (gap의 경제성)

- **쉬운 말로**: *잘 만든* diverse/quality injected failure가 student-mined랑 **실성능 차이가 거의 없을** 가능성. 그럼 "비싸게 student rollout 했는데 이득 미미" → 기여가 격하됨.
- **검증**: ❌ **근거 없음(2026-06-03 정정)** — 이전엔 "synthetic-data 문헌이 quality/diversity > distribution-matching을 시사"라 적었으나, 직접 fetch해보니 인용 3편이 *지지 안 함*: 2410.15226은 정반대(diversity↔성능 양의 상관), 2412.02980은 dist-matching과 비교 안 함, 2502.08661(SynAlign)은 오히려 dist-matching이 중요하다는 논문. → **R5는 literature-backed가 아니라 순수 우리 추측.** (그래도 *위험 자체*는 ablation으로 직접 재야 하므로 유지.)
- **죽냐/사냐**: `student-mined vs well-engineered-injected` head-to-head에서 **통계적으로 유의한 격차**를 못 보이면 위험. (근거가 추측이라, 이 head-to-head는 방어가 아니라 *발견* 실험에 가까움.)

---

## 3. 그래서 죽냐 사냐 — 한눈 정리

- **gap의 존재 자체**: 🟢 단단함. (이론: imitation learning covariate shift / DAgger. 실증: Wu et al.)
- **비어 있는 칸 (우리 자리)**: 🟢 **terminal 도메인 × student-on-policy mined recovery × (특히) RL까지** = 교집합은 아직 아무도 안 함.
- **진짜 위험의 우선순위 (방법 정정 후)**: **[N2 hint-leak] ≈ [N1 incremental] > R1(잔여) > R4 > R5.** (R2는 사실상 해소, R3은 약화 — 아래.)
  - **R2(모티베이션 선점) = 해소/자산**: 우리는 TermiGen motivation에 *동의하고 그 위에서* 해결책을 제안 → 문제를 우리가 증명 안 해도 SOTA가 해줌.
  - **R3(Wu scoop) = 약화**: "injected≠real"을 헤드라인 아닌 supporting 증거로, 그것도 Wu가 안 한 *terminal*에서.
  - **R1 = 🔴→🟠**: 복구가 teacher 시연이 아니라 *student 자신의 hint-guided 생성*이라 covariate shift가 작음(§2 R1 정정).
  - **새 top 리스크 둘**: **(N1) incremental** — 메커니즘이 STaR-계열이라 novelty를 "조합·도메인·실측"으로 세워야. **(N2) hint-leak** — test엔 힌트 없음; 힌트 덕분에만 복구하면 배운 건 "복구"가 아니라 "힌트 읽기" → hint-free ablation이 생사.

**한 줄 결론**: *gap은 진짜고, 제안 방법(student 실패 + hint-guided self-recovery)은 R1을 설계로 상당 부분 피해간다.* 남은 진짜 질문은 "**injected를 TerminalBench에서 실제로 이기나**(N1)" + "**힌트 빼도 복구가 남나**(N2 hint-free)". 첫 실험은 이 둘을 가르는 ablation이어야 함.

---

## 4. 추천 재프레이밍 (R2/R3 방어)

> ❌ "우리는 expert trajectory가 student 실수를 안 담는 mismatch를 발견했다"
> ✅ **"TermiGen은 *문제*는 잡았지만 *해결책*이 여전히 generator-critic injection이다. Wu et al.(2512.02389)이 보였듯 injected는 on-policy로 전이 안 된다. 우리는 TermiGen 바로 그 Harbor 환경에서 target student를 rollout해 *걔가* 깨지는 state를 mining하고, 그 state에 recovery를 supervise한다 — off-policy injection을 student-aligned on-policy recovery로 바꾼다."**

방어 효과: ① baseline의 문제선점을 인정하되 *solution gap*으로 이동, ② Wu et al.을 *내 발견*이 아니라 *TermiGen 비판 근거*로 재배치, ③ 같은 환경 재사용이라 head-to-head ablation이 깔끔.

---

## 5. 🟦 Codex에게 묻는 검토 포인트

1. **방법 정정 반영.** 우리 방법은 *teacher가 복구를 시연*하는 게 아니라 **teacher 힌트 + student 자가복구 생성 → SFT**(STaR식)다. 이렇게 하면 R1(off-policy label)을 상당 부분 피하나? 아니면 "고정 데이터셋 SFT"라는 점에서 여전히 순수 RL 대비 본질적 한계가 있나? **RL arm을 ceiling으로 둘 가치**가 있나? 그리고 **(N2)** 힌트가 test에 없는데, hint-free에서 복구가 내재화될 거란 보장이 있나 — 이걸 키우는 학습/데이터 설계는?
2. **수집 정의**: "student가 깨지는 지점(failure state)"을 어떻게 정의/추출하는 게 best인가? (예: reward=0 trajectory의 earliest-critical-error vs irreversible state corruption 분류 vs step-level value drop) — AgentDebug(2509.25370) taxonomy를 terminal로 가져오는 게 맞나?
3. **R5 사전 방어**: "injected 분포 vs student-mined 분포"의 거리를 *coverage*가 아니라 *conditional* 하게 정량화할 metric이 뭐가 좋나? (단순 커버리지는 Wu et al.이 95%여도 실패한다고 보임.)
4. **차별화 충분성**: DAgger-LLM(2605.12913)/OEC(2512.14895)가 SWE에서 이미 on-policy correction을 했다. 우리 contribution이 **"terminal 도메인 실증 + recovery-data 산출물"** 하나로 충분한가? 부족하면 무엇을 더해야 방어 가능한가? (예: RL arm 필수화? failure taxonomy 공개? cross-student 일반화?)
5. **실험 우선순위**: §3의 첫 ablation(`injected-SFT` vs `student-mined-SFT` vs `student-mined+RL`, 동일 Harbor 환경, TerminalBench pass-rate)이 go/no-go 판단으로 충분한가? 더 싸게 신호를 얻을 minimal pilot이 있나?

---

## 6. 정직성 노트 — 검증 상태 (2026-06-03 업데이트)

- ✅ **deep-research 크래시분 재검증 완료**: adversarial-verify 단계가 크래시해 미검증으로 남았던 `survey/related-work-survey.md`의 나머지 9개 출처를 **직접 fetch해 사후 검증**(상세: survey Appendix C). **9개 전부 실재 — 지어낸 ID 없음.** 단 attribution 정밀도 정정 다수.
- ⚠️ **R5 근거 붕괴(위 정정 반영)**: 인용 3편 중 하나(2410.15226)는 정반대, 둘(2412.02980·2502.08661)은 무관/역방향 → R5는 literature-backed 아님.
- ⚠️ **나머지 정정**: TerminalTraj(2602.01244) 진짜 제목 + teacher-only 미확인 / AgentHER(2603.21357) "Replay"·수치 벤치별 분리 / Rethinking-OPD(2604.13016) main thrust는 thinking-pattern consistency / Terminal-Bench(2601.11868) v1.0·v2.0 날짜·소속만 미확인.
- 이번 검증도 **abstract + (가능 시) HTML 본문**까지. 각 논문 세부 방법/한계 full read는 인용 직전 권장. terminal-bench v1.0/v2.0 날짜·"Stanford+Laude" 소속은 tbench.ai에서 별도 확인 필요(유일한 미해결).

---

## 7. Novelty prior-art check (2026-06, 추가 타겟 검증)

deep-research 본조사 뒤, "hint-guided student self-recovery for agents" 정확 조합을 직접 타겟 검색·fetch함. **결론: self-correction / agent-recovery 동네는 붐비지만, 우리 정확한 칸(②½ × terminal)은 비어 있다. 단 N1(incremental)이 main risk로 부상.**

| 논문 | 실패 출처 | 복구 생성자 | 학습 | 도메인 | scoop? |
|---|---|---|---|---|---|
| **From Correction to Mastery** (2509.14257) | student on-policy ✅ | **teacher가 step 통째 교체(②)** | SFT+DPO+RL | math/QA/web — **terminal 아님** | **최근접 neighbor, scoop 아님** |
| PALADIN (2509.25238) | **injection** | student-gen(annotated) | SFT | tool-use API | ❌(①측) |
| Synthetic Self-Reflected (2505.20023) | **injection** | self-reflect+partial mask | SFT | tool-use/planning | ❌(①측) |
| STaSC (2503.08681) | student self ✅ | student(힌트 없음) | iterative SFT | **single-turn QA** | ❌ (단 *internalization* 증거 = N2 우호) |
| SCoRe (2409.12917) | student self ✅ | student | **RL** | math/code | ❌(③) |
| START | hint-infer | student(hint) | RFT | tool-invocation reasoning | ⚠️ 메커니즘만 |

**중립 재확인 (2509.14257)** — verbatim: *"πE provides a minimal intervention by replacing σk with a corrected step σk′, and the student resumes from (σ1,…,σk−1,σk′)"*. → teacher가 **정답 step을 직접 써주고(②)** student는 이어받음. **우리 ②½(hint만 주고 student가 복구를 자기가 생성)와 다름.** terminal 평가도 없음(AIME/MATH500/HotpotQA/GAIA/WebWalker…).

**살아남는 wedge (정확히)**: ① 실패=student on-policy + ② 복구=**hint-guided student self-gen (②½, teacher-correction ②와 구별)** + ③ **terminal** + ④ **injected(TermiGen ①)와 head-to-head**. 이 교집합은 비어 있음.

**그러나 N1(incremental) 부상**: ②(From Correction to Mastery)와 ③(SCoRe류 RL)이 이미 점유 → reviewer는 "②½가 ② 대비 뭘 더 주냐"를 물음. **방어 = ②½ > ② 를 깔끔히 실측** (원리: hint-only면 복구가 student 분포에 남아 더 imitable·낮은 covariate shift — STaR 논리). 이 **②-vs-②½ 비교 자체가 핵심 contribution**이 될 수 있음.

**→ 추천 ablation 4-arm**: **① injected-SFT (TermiGen) / ② teacher-correction-SFT (From-Correction-to-Mastery식) / ②½ hint-guided self-recovery-SFT (ours) / ③ student-mined + RL** — 동일 Harbor 환경, TerminalBench pass-rate.

---

*근거 전문: `survey/related-work-survey.md` (deep-research 본 리포트 + Appendix B). Prior-art 검증 로그: 본 문서 §1·§7.*

## 차별점 보강 (2026-06-04) — 복구 *검증의 엄격함* (verbatim 근거 기반)

TermiGen도 복구를 학습한다(공통). 추가 차별점 = **복구가 "진짜 복구"임을 어떻게 보장하느냐**:

- **TermiGen**: 복구(correct-intent step)는 **Critic = Claude-4.5(생성과 동일 모델)**가 *실행 후
  결과를 보고* "상태를 효과적으로 진전시켰나"를 **주관적으로 판단**(self-grading). 판단 rubric/프롬프트는
  논문 비공개. 최종 SFT는 verifier로 **거르지 않음**(τ=0%, 실패 포함). → 복구 품질관리 = **soft,
  same-model, 기준 비공개 LLM 판단**.
- **우리 ②½**: 복구는 **student 자신이 자가복구**하고, 그 trajectory가 **실제 환경 test.sh를
  통과(reward 0→1)** 해야만 recovery 데이터로 채택 = **hard, objective ground-truth gate**.

→ 셀링포인트: *"TermiGen은 teacher의 복구를 같은 LLM이 soft self-validate하지만, 우리는 복구가
실제 환경 검증을 통과함을 요구한다."* (주의: "TermiGen이 복구를 안 본다"가 아니라 "soft-validate
한다"로 표기.)

**단, TermiGen이 LLM Critic을 쓴 *합리적 이유*도 인정**: test.sh는 task *최종 목표*만 검증하므로
**중간 step**(복구는 보통 task 중간에 일어남)을 per-step으로 hard-검증할 방법이 없다 → 중간 step
품질엔 LLM judge가 현실적. 우리는 per-step이 아니라 **복구 완료 후 end-to-end 최종 결과**로 hard-검증.
즉 granularity가 다름(TermiGen=per-step soft / 우리=end-to-end hard).
