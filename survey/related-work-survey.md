# Related Work Survey (Contrarian / Gap-May-Be-Weak Angle)

> 평가 대상 THESIS: **"Terminal agent의 recovery-training data는 teacher가 만든/스크립트로 주입한 failure(Bernoulli error injection, deliberate typo, generator-critic perturbation)가 아니라, 실제 target student를 직접 roll out해서 student가 진짜로 깨지는 지점을 mining한 on-policy failure distribution에 맞춰야 한다. Agent failure는 distributional하므로 recovery supervision은 idealized teacher가 아니라 deployed student에 align되어야 한다."**

이 문서는 위 thesis를 **회의적(contrarian) 관점**에서 stress-test한다. 핵심 질문: *(a) scripted/injected failure가 정말로 real failure와 distribution이 다른가? (b) distribution을 맞추는 것이 정말로 robustness/recovery에 측정 가능한 차이를 만드는가? (c) 이 아이디어가 이미 published되어 scoop당했는가?* 아래 결론을 먼저 요약하면: **gap 자체는 진짜다 (이미 실증 논문이 존재). 하지만 그 실증 논문의 존재가 곧 scoop 위험이고, 동시에 "distribution을 SFT로 맞추는 것만으로 충분한가"라는 더 깊은 위협을 시사한다.**

---

## 1. PRIOR ART / NOVELTY — 가장 중요

### 1.1 결론 요약
- **Terminal/CLI 도메인 한정**으로는, student의 on-policy failure를 직접 mining해서 recovery trajectory를 합성하는 *정확히 그 방법*을 publish한 논문은 아직 못 찾았다. 하지만 **TermiGen (arXiv:2602.07274)** 이 *동일한 문제 정의*("expert trajectory가 small model의 실수를 안 보여줘서 distributional mismatch가 생긴다")를 이미 명시적으로 제기했고, scripted/generator-critic injection으로 *해결을 시도*했다. 즉 **문제 framing은 이미 점유됨**, novelty는 *solution 메커니즘*(student-on-policy mining)에만 남는다.
- **General LLM-agent 도메인**으로 넓히면 scoop 위험이 급격히 커진다. 특히 두 논문이 thesis의 핵심 주장을 이미 publish했다:
  1. **Wu, Kapur, Sahai, Russell — "Synthetic Error Injection Fails to Elicit Self-Correction In Language Models" (arXiv:2512.02389, 2025-12)**: thesis의 *실증적 핵심*("injected error ≠ on-policy error, 그리고 injected로 학습하면 on-policy로 일반화 실패")을 **controlled experiment로 이미 증명**. 이것이 가장 위험한 scoop — thesis의 가장 강한 근거가 *남이 이미 쓴 논문*이다.
  2. **"Where LLM Agents Fail and How They can Learn From Failures" / AgentDebug (arXiv:2509.25370, 2025-09)**: agent 자신의(self-generated, on-policy) failure trajectory를 수집·진단하고 recovery를 유도하는 framework. general-agent 버전의 thesis와 상당히 겹친다.

### 1.2 가장 가까운 기존 연구와 scoop 근접도 평가

| 논문 | 무엇을 하는가 | thesis와의 거리 | scoop 위험 |
|---|---|---|---|
| **Wu et al. 2512.02389** "Synthetic Error Injection Fails..." | Multiplication/Sudoku controlled task에서 synthetic error 주입 SFT가 on-policy error 교정으로 일반화 실패함을 증명. >95% 커버리지에도 실패. | thesis의 *전제(injected≠on-policy, mismatch가 해롭다)*를 거의 그대로 입증. 단 domain은 toy reasoning task이고, "그럼 student-mined SFT로 고쳐진다"는 *해결책은 안 줌* (오히려 RL을 가리킴). | **매우 높음 (전제 부분)**. thesis가 "이 mismatch가 문제다"를 contribution으로 내세우면 곧바로 "이미 2512.02389가 보였다"로 반박당함. |
| **TermiGen 2602.07274** | Terminal agent용 환경+resilient expert trajectory 합성. Generator-Critic이 trajectory 수집 중 error를 *능동 주입*. TerminalBench 31.3% SOTA. | **동일 도메인 + 동일 문제 정의**. "expert trajectory가 small model 실수를 안 보여준다 → student가 자기 runtime failure 복구를 못 한다"를 명시. 단 solution은 *scripted/injected* (student rollout mining 아님 — abstract 기준). | **높음 (문제/baseline 부분), 중간 (solution 부분)**. 문제는 점유됨. 차별화는 solution이 student-on-policy냐에 달림. |
| **AgentDebug / 2509.25370** | AgentErrorTaxonomy + AgentErrorBench(ALFWorld/GAIA/WebShop의 *real rollout* 실패 annotation) + earliest-critical-error 진단 후 re-rollout. | general-agent 버전 thesis와 매우 근접. real(on-policy) 실패에서 학습한다는 점이 핵심적으로 겹침. 단 *주력은 진단/benchmark*이고 "deployed student에 matched된 recovery SFT data 합성"이 main claim인지는 *원문 정독으로 재확인 필요* (web 요약은 과대해석 경향). | **중간~높음**. terminal-specific은 아니지만 "self-induced failure에서 recovery 학습" 컨셉을 선점. |
| **"Exploring Expert Failures Improves LLM Agent Tuning" (arXiv:2504.13145)** | RFT를 *실패한* expert trajectory의 유용한 중간 step까지 활용하도록 확장. failure에서 학습. | 인접. 단 "expert(teacher) failure"를 쓰지 "student own failure distribution matching"이 핵심은 아님. | 중간. failure-from-data 아이디어 선점하지만 on-policy-student 각도는 약함. |
| **On-Policy Distillation (Thinking Machines, 2025) / "A Survey of On-Policy Distillation" (arXiv:2604.00626)** | student가 자기 trajectory를 sampling하고 teacher가 token-level로 채점. compounding error/exposure bias를 student 자기 error state 노출로 완화. | thesis의 *이론적 토대*(student own error state에 노출되어 recovery 학습)와 정확히 같은 논리. 단 terminal/recovery-data 특화는 아님 — 일반 distillation. | 중간. 메커니즘 일반론은 선점, terminal recovery-data 적용은 비어있음. |

**Novelty 판정**: "student-induced, failure-distribution-matched recovery data **for terminal/CLI agents**"라는 *교집합*은 아직 비어 있는 것으로 보인다. 그러나 이 교집합의 세 구성요소(① mismatch가 문제다, ② on-policy/self-generated failure에서 학습, ③ terminal-agent trajectory 합성)는 각각 이미 강하게 점유됨. **순수 conceptual novelty는 낮고, "기존 조각들의 specific composition + terminal 도메인 실증"이 novelty의 전부.**

---

## 2. VIABILITY / EVIDENCE — gap이 진짜이고 중요한가? (contrarian 핵심)

### 2.1 (a) injected/teacher failure가 정말 real failure distribution과 다른가? → **YES, 실증됨**
**Wu et al. 2512.02389**가 결정적 증거다. controlled task(4-digit multiplication, 4×4 Sudoku)에서:
- synthetic error 주입 분포가 on-policy error mode를 **>95% 커버**해도, 모델은 *synthetic error만* 신뢰성 있게 교정.
- on-policy error로 가면 성능 붕괴: recognition rate가 Qwen2.5/Sudoku에서 **94%→8%**, Gemma-3/multiplication에서 **83%→20%**. correction rate는 Qwen2.5/multiplication에서 **99%→40%**.
- 교정 실패 시 25%는 *원래 error를 그대로 반복*.

이는 thesis의 (a) 전제를 강하게 지지한다. **단 contrarian 주석**: 이 결과는 *toy arithmetic/puzzle*에서 나온 것이고, terminal-agent의 multi-step tool-use failure(잘못된 flag, 존재하지 않는 path, 권한 오류 등)로 *동일하게 전이된다는 보장은 없다*. terminal failure는 종종 환경 feedback(stderr, exit code)이 명시적이라, "self-correction을 elicit"하는 난이도가 reasoning task와 다를 수 있다. → thesis는 **terminal 도메인에서 mismatch가 실재함을 자체적으로 다시 측정**해야 하며, 2512.02389를 그대로 인용해 "증명 끝"이라 주장하면 약하다.

### 2.2 (b) train/deploy distribution mismatch가 측정 가능하게 robustness를 해치는가? → **YES, 이론+실증 모두**
- **이론(covariate shift / DAgger)**: imitation learning에서 expert state 분포로만 학습한 policy는 자기 실수로 *벗어난 state*에서 행동을 모른다 → error가 horizon에 따라 quadratic하게 compound (Ross et al. DAgger의 고전 결과). On-policy correction(student가 방문하는 state에 supervision을 추가)이 이를 linear로 낮춘다. terminal agent는 long-horizon이라 이 효과가 *증폭*된다. **이 이론적 backing은 thesis를 강하게 지지** — 가장 단단한 기둥.
- **실증(agent 논문)**: On-Policy Distillation 계열(Thinking Machines blog; arXiv:2604.00626 survey; arXiv:2604.13016 "Rethinking On-Policy Distillation")이 "off-policy student는 teacher가 자주 가는 context에서만 학습 → 자기 초기 실수로 divergence 증폭"을 반복적으로 보고. AgentDebug(2509.25370)는 "early root-cause error가 cascade되어 trajectory 전체를 망친다"를 ALFWorld/GAIA/WebShop *real rollout*에서 보임.

### 2.3 contrarian — gap이 "생각보다 약할" 두 가지 경로

이 thesis의 viability를 위협하는 *진짜 위험*은 "gap이 없다"가 아니라 아래 두 가지다:

**(R1) Distribution을 SFT로 맞추는 것만으로는 부족할 수 있다 (해결책 무효화 위험).**
2512.02389의 *가장 불편한* 디테일: synthetic error가 on-policy error를 **>95% 커버해도** SFT는 실패했다. 즉 단순 *커버리지/분포 매칭*이 충분조건이 아니다. 저자들은 명시적으로 결론을 **on-policy RL이 uniquely effective**한 쪽으로 끌고 간다("successful self-correction requires more precisely matching error distributions... suggesting why on-policy methods like RL have proven uniquely effective"). 
→ 함의: thesis가 "student-mined failure로 **SFT** recovery data 만들기"라면, *데이터를 student 분포에서 뽑아도 여전히 SFT라는 학습 방식 자체의 한계*에 부딪힐 수 있다. "on-policy data를 모았다"와 "on-policy로 학습했다(RL)"는 다르다. **이것이 thesis의 단일 최대 약점.** student rollout으로 mining하지만 결국 teacher가 recovery를 시연하고 그걸 SFT한다면, 학습 신호는 여전히 off-policy expert label이다.

**(R2) "분포 매칭"의 한계효용이 작을 수 있다 (gap의 경제성 위험).**
> ⚠️ **2026-06-03 검증 후 정정**: 이 단락의 근거로 든 synthetic-data 3편은 직접 fetch해보니 *우리 주장을 뒷받침하지 않는다*. (a) **arXiv:2410.15226**은 "diversity가 in-distribution 일반화를 안 늘린다"의 **정반대**("diversity가 pretraining/SFT 성능과 양의 상관")를 말함 — **오인용**. (b) **arXiv:2412.02980**은 quality→in-distribution / diversity→OOD / complexity→both로 나눌 뿐 *distribution-matching과 비교 자체를 안 함*. (c) **arXiv:2502.08661(SynAlign)**은 오히려 *distribution-matching이 중요하다*는 논문이라 결이 반대. → **R5는 literature-backed가 아니라 순수 우리 추측으로 강등.** 아래 원문은 보존하되 근거 없음으로 읽을 것.
>
> synthetic-data 문헌이 *quality/diversity가 distribution-matching보다 downstream 성능 분산을 더 많이 설명*한다고 보고하는 경향이 있다 ~~(arXiv:2410.15226; 2412.02980; 2502.08661)~~. 즉 *충분히 다양하고 질 좋은* teacher/injected failure가 student-mined failure와 *실질 성능에서 구별 안 될* 가능성. → thesis는 "student-mined vs well-designed-injected"의 **head-to-head ablation에서 통계적으로 유의한 격차**를 보여야 한다. 그 격차가 작으면 "engineering 한 비용 대비 이득 없음"으로 격하될 위험. (단 위 정정대로, 이 위험의 *방향*은 literature가 아니라 추론에 기댄다.)

**종합 viability 판정**: gap의 *존재*는 단단하다(이론+2512.02389). 하지만 thesis가 제안하는 *형태*(student-mined → recovery SFT)가 그 gap을 *실제로 닫는다*는 보장은 약하다. 위험은 "gap이 없다"가 아니라 "**(R1) 같은 데이터라도 SFT로는 못 닫는다**" + "(R2) **잘 만든 injected와 차이가 작다**" 두 가지다.

---

## 3. METHOD LANDSCAPE — agent error-recovery / recovery-data 생성 방법 지도

각 방법이 *deployed student의 failure 분포에 매칭되는지* 표기 (✅ 매칭 / ⚠️ 부분 / ❌ 비매칭).

| 방법군 | 대표 | 메커니즘 | student 분포 매칭? |
|---|---|---|---|
| **Error injection / perturbation** | TermiGen Generator-Critic; Bernoulli/stochastic fault injection; deliberate typo | trajectory 수집 중 인위적 fault 주입 후 recover 시연 | ❌ (teacher/scripted 분포; 2512.02389가 일반화 실패 보임) |
| **Recovery/correction trajectory synthesis** | TermiGen resilient trajectory; expert가 만든 error-correction cycle | expert가 error→diagnose→recover 시퀀스를 생성 | ❌~⚠️ (expert가 만든 error는 smaller student의 error와 다름 — TermiGen 스스로 인정) |
| **Self-correction (inference-time)** | Reflexion; Self-Refine | 모델이 자기 출력을 reflect/critique 후 수정, 학습 X | ⚠️ (자기 출력 기반이라 on-policy지만, 학습 데이터화/SFT는 아님; gain은 model이 이미 교정 능력 있을 때만) |
| **On-policy / DAgger-style data** | DAgger; On-Policy Distillation; AgentDebug re-rollout | student가 방문한 state에서 expert label 질의 → 그 state에 supervision | ✅ (state 분포는 student; 단 label은 여전히 expert=off-policy 신호) |
| **RL from own mistakes** | RL self-correction (arXiv:2409.12917); GRPO terminal RL (terminal-bench-rl) | student rollout의 verifiable reward로 정책 직접 업데이트 | ✅✅ (분포+신호 모두 on-policy; 2512.02389가 가리키는 정답에 가장 근접) |
| **SFT from own correct rollouts** | STaR / RFT / Rejection sampling | student가 성공한 trajectory만 골라 SFT | ⚠️ (성공만 봄 → *failure recovery*는 거의 안 가르침; 쉬운 subtask 편향) |
| **SFT from own/expert failures** | "Exploring Expert Failures" (2504.13145) | 실패 trajectory의 유용한 부분을 SFT/DPO 신호로 | ⚠️ (expert failure 중심; student-own-failure-matched는 아님) |
| **Agent instruction-tuning data** | AgentInstruct; AgentTuning류 | 다양한 agent task의 expert demonstration 대량 합성 | ❌ (전형적 off-policy expert; failure recovery 비중 낮음) |

**관찰**: "student 분포 매칭"을 *가장 잘 달성하는* 방법군은 **RL from own mistakes**다. thesis가 SFT(recovery-data 합성)에 머무르면, landscape 상에서 자신이 비판하는 off-policy label 문제를 *데이터 출처만 바꾼 채* 그대로 안고 갈 수 있다. **가장 방어 가능한 위치는 "student-mined failure state + 거기서의 recovery를 RL(또는 DAgger처럼 student-state-conditioned)로 학습"** 이지, 단순 "student failure 위에 teacher recovery를 SFT"가 아니다.

---

## 4. POSITIONING vs BASELINES

### 4.1 TermiGen (arXiv:2602.07274) — **존재 확인됨, placeholder 아님**
README가 인용한 ID는 **실재하는 논문**이다.
- **제목**: *"TermiGen: High-Fidelity Environment and Robust Trajectory Synthesis for Terminal Agents"*.
- **무엇을 하나**: verifiable 환경(Docker task) 합성 + "resilient expert trajectory" 합성. 핵심은 **Generator-Critic protocol이 trajectory 수집 중 error를 능동 주입**해 error-correction cycle이 풍부한 데이터를 만든다. TermiGen-Qwen2.5-Coder-32B가 **TerminalBench 31.3%** SOTA.
- **문제 정의 (thesis와 충돌하는 부분)**: TermiGen abstract가 *이미* 명시 — "standard instruction tuning uses expert trajectories that rarely exhibit simple mistakes common to smaller models. This creates a **distributional mismatch**, leaving student models ill-equipped to recover from their own runtime failures." → **thesis가 내세우려는 문제의식을 TermiGen이 선점**.
- **결정적 차이점 (thesis 유리)**: TermiGen의 error는 **Generator-Critic가 주입**한다 — 즉 *injection 분포가 student가 아니라 generator/critic(teacher측)에 의해 결정*. abstract는 on-policy, student rollout mining, DAgger를 **언급하지 않음**. README가 TermiGen을 "teacher-generated resilient trajectories / Bernoulli·generator-critic perturbation"으로 규정한 것은 이 메커니즘과 정합적.

### 4.2 Terminus / TerminalBench
- **TerminalBench (arXiv:2601.11868)** "Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces" — 실제 CLI 환경(인터넷 접속, 패키지 설치 허용)에서 agent를 평가하는 *벤치마크*. thesis의 *평가 무대*이지 baseline 방법이 아님. **Terminus**는 그 위에서 도는 agent harness/스캐폴드 계열. 이들은 "어디서 측정하느냐"를 제공하므로, thesis는 *TerminalBench pass-rate에서 student-mined recovery data가 injected 대비 우월함*을 보이는 형태로 positioning해야 한다.

### 4.3 가장 깨끗하고 방어 가능한 차별화 (vs TermiGen)
TermiGen이 문제의식을 선점했으므로, thesis는 **"우리도 같은 mismatch를 본다"가 아니라 "TermiGen의 *해결책*이 그 mismatch를 충분히 닫지 못한다"**로 각을 세워야 한다. 정확히:

> *"TermiGen recovers the **problem** (expert traces lack the student's mistakes) but its **solution still injects failures from a generator-critic, not from the student itself**. Per Wu et al. (2512.02389), even >95% coverage of on-policy errors by a synthetic injector fails to transfer; recovery must be conditioned on the *student's actual* failure states. We close the loop by **rolling out the target student on TermiGen's environments, mining where *it* breaks, and supervising recovery on those states** — turning TermiGen's off-policy injection into student-aligned, on-policy recovery."*

이 framing의 강점: (1) baseline의 *문제 선점*을 인정하되 *solution gap*으로 칼끝을 옮김, (2) 2512.02389를 *내 주장의 근거*가 아니라 *TermiGen 비판의 근거*로 재배치(스쿱 방어), (3) TermiGen 환경을 *재사용*하므로 head-to-head ablation(injected vs student-mined, 환경 고정)이 자연스럽고 강력.

---

## VERDICT (candid)

**이 방향은 novel하고 추진할 가치가 있는가?** — **조건부 YES, 단 "약한 novelty + 실재하는 scoop 위험"을 안고 있다.** terminal/CLI 도메인에 한정하면 "student-on-policy mined recovery data"라는 *정확한 조합*은 아직 비어 있다. 하지만 그 조합의 모든 구성요소는 이미 강하게 점유됐다.

**가장 큰 risk는 무엇인가?** — 둘 다 실재하지만 우선순위가 있다:
1. **(스쿱) Wu et al. 2512.02389가 thesis의 실증적 핵심을 이미 publish함.** "injected≠on-policy, 그리고 injected SFT는 on-policy로 일반화 실패" — 이게 thesis의 main empirical claim이면 *이미 나온 결과*다. → 방어: terminal 도메인에서 *다시* 측정 + 2512.02389를 TermiGen *비판 근거*로 재배치. 단순 "우리가 mismatch를 발견" 톤은 금물.
2. **(gap이 생각보다 약함 — 더 깊은 위험) "데이터를 student에서 뽑아도, SFT로는 그 gap을 못 닫을 수 있다."** 2512.02389 자체가 *커버리지 충분해도 SFT 실패 → RL 필요*를 가리킨다. thesis가 "student-mined failure + teacher recovery SFT"면, *데이터 출처만 on-policy이고 학습 신호는 여전히 off-policy expert label*이라 자기가 비판한 문제를 그대로 안는다. 추가로 synthetic-data 문헌은 "잘 만든 diverse/quality injected가 분포 매칭보다 중요"라고 시사 → student-mined vs well-engineered-injected의 격차가 *통계적으로 작을* 위험.

→ **둘 중 더 치명적인 것은 2번(gap-may-be-weak)이다.** 1번은 framing으로 우회 가능하지만, 2번은 *실험에서 진짜로 차이가 안 나면* thesis 자체가 무너진다. 따라서 **early ablation 1순위**: (i) 같은 TermiGen 환경에서 *injected-recovery-SFT* vs *student-mined-recovery-SFT*를 TerminalBench pass-rate로 head-to-head, (ii) 거기에 *student-mined + RL(or DAgger-style on-policy label)* arm을 추가해 "데이터만 바꾸는 것 vs 학습신호까지 on-policy로" 분해. (i)에서 격차가 안 나오거나 (ii)에서 RL arm만 이기면 thesis는 재구성 필요.

**가장 강한 contribution framing 2~3개:**
1. **"Closing TermiGen's solution gap" (최우선)**: 같은 환경·같은 task 분포에서 *off-policy injected recovery* (TermiGen 식) vs *student-on-policy mined recovery*를 통제 비교해, terminal 도메인에서 *injected가 student failure로 전이 안 됨*을 **직접 실측**하고 pass-rate 격차를 보이기. (2512.02389의 toy 결과를 *agentic terminal*로 확장 — 이건 진짜 비어 있는 실증.)
2. **"On-policy data ≠ on-policy training" 분해**: student-mined-state 위에서 (a) teacher-recovery-SFT vs (b) RL/DAgger-style on-policy 신호를 분리 측정. (R1) 위험을 *정면으로* 다루면 reviewer 선제 방어가 되고, "데이터 출처 + 학습 신호" 2차원 ablation 자체가 기여가 됨.
3. **"Student-aware failure taxonomy for terminal agents"**: AgentDebug(2509.25370)의 taxonomy 아이디어를 terminal로 가져와, *student가 실제로 깨지는 failure mode 분포*를 측정·공개하고 injected 분포와의 거리를 정량화(coverage가 아니라 *conditional* mismatch). 데이터/벤치 기여로서 SFT-vs-RL 논쟁과 독립적으로 살아남음.

**한 줄 요약**: gap은 진짜지만 *thesis가 제안한 형태로 그 gap이 닫힌다는 보장이 약하다*. 추진하되, 첫 실험은 "novelty 증명"이 아니라 **"student-mined가 injected를 TerminalBench에서 실제로 이긴다, 그리고 그게 SFT만으로 되는지 RL이 필요한지"**를 가르는 ablation이어야 한다.

---

## Sources
- Wu, Kapur, Sahai, Russell. "Synthetic Error Injection Fails to Elicit Self-Correction In Language Models." arXiv:2512.02389. https://arxiv.org/abs/2512.02389 / https://arxiv.org/html/2512.02389
- "TermiGen: High-Fidelity Environment and Robust Trajectory Synthesis for Terminal Agents." arXiv:2602.07274. https://arxiv.org/abs/2602.07274
- "Where LLM Agents Fail and How They can Learn From Failures" (AgentDebug). arXiv:2509.25370. https://arxiv.org/abs/2509.25370
- "Exploring Expert Failures Improves LLM Agent Tuning." arXiv:2504.13145. https://arxiv.org/abs/2504.13145
- "Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces." arXiv:2601.11868. https://arxiv.org/html/2601.11868v1
- "A Survey of On-Policy Distillation for Large Language Models." arXiv:2604.00626. https://arxiv.org/pdf/2604.00626
- "Rethinking On-Policy Distillation of Large Language Models." arXiv:2604.13016. https://arxiv.org/html/2604.13016v1
- On-Policy Distillation. Thinking Machines Lab. https://thinkingmachines.ai/blog/on-policy-distillation/
- "Training Language Models to Self-Correct via Reinforcement Learning." arXiv:2409.12917. https://arxiv.org/pdf/2409.12917
- "On the Diversity of Synthetic Data and its Impact on Training Large Language Models." arXiv:2410.15226. https://arxiv.org/html/2410.15226v2
- "Surveying the Effects of Quality, Diversity, and Complexity in Synthetic Data From Large Language Models." arXiv:2412.02980. https://arxiv.org/html/2412.02980v1
- "Few-shot LLM Synthetic Data with Distribution Matching." arXiv:2502.08661. https://arxiv.org/html/2502.08661v1

---
---

# Appendix B: Terminal/CLI-Agent Domain Prior Art (보완 조사)

> 이 부록은 위 contrarian 조사와 **상보적**이다. 각도: terminal 배포 도메인(Terminal-Bench, Terminus, Harbor)에 핀을 고정해, terminal-agent에서 *failure-mined recovery supervision*을 이미 한 논문이 있는지와 도메인 특화 recovery-data 방법을 표면화한다. 위 본문이 못 다룬 **TermiGen injection 메커니즘의 verbatim 디테일**과 **DAgger-style LM-agent 논문들**을 추가한다.

## B.1 TermiGen injection 메커니즘 — HTML 정독으로 확인 (가장 중요)
arXiv:2602.07274 본문(html v1) fetch 결과, README가 "Bernoulli intent sampling, 5 failure categories, Generator-Critic"이라 규정한 것은 **정확**하다:
- **누구의 trajectory에 주입하나**: backbone = **Claude-4.5-Sonnet (teacher)**. 즉 **target student(Qwen2.5-Coder-32B)를 rollout하지 않는다.** failure는 teacher에게 *"sophisticated error를 commit하라"*고 지시해 생성 → idealized/imagined 분포.
- **Bernoulli intent sampling**: *"If I_t = ℐ_correct, the agent aims to advance the task state. Conversely, if I_t = ℐ_error, the agent is instructed to commit a sophisticated error."* injection rate **ε = 0.2 (고정)**.
- **5 failure categories**: ① Analysis Errors ② Command Errors ③ Hallucinations ④ Requirement Violations ⑤ Verification Failures.
- **자인한 한계**: *"we currently implement a simple agent without a memory component."* student-discovered failure가 아니라 fixed-rate scripted injection임을 스스로 드러냄.

→ **함의 (본문 §4.3 보강)**: TermiGen은 *문제 framing*("recover from their own runtime failures")은 선점했지만, *failure source*는 명백히 teacher-side injection이다. thesis의 "student-mined" wedge는 메커니즘 차원에서 살아 있다.

## B.2 가장 가까운 method scoopers — DAgger를 LM agent에 적용 (본문이 누락)
본문은 Wu(2512.02389)·AgentDebug(2509.25370)에 집중했으나, **on-policy student-rollout + teacher correction을 LM agent에 직접 구현한** 두 논문이 method 차원에서 더 가깝다:

| 논문 | 핵심 | student rollout? | terminal? | recovery-data 합성? | scoop |
|---|---|---|---|---|---|
| **Revisiting DAgger in the Era of LLM-Agents** (arXiv:2605.12913) | student/teacher turn을 βᵢ로 stochastic mix, *모든 visited state에서 expert action query*. covariate shift 명시 | **예** | ❌ (SWE) | 부분(teacher-interleaved DAgger recipe) | ★★★★☆ |
| **Imitation Learning for Multi-Turn LM Agents via On-Policy Expert Corrections** (arXiv:2512.14895) | student rollout → 실패 state에서 expert correction(OEC). SWE-Gym/SWE-Bench Verified, 4B/8B student | **예** | ❌ (SWE) | 부분(on-policy correction data) | ★★★★☆ |

- 2605.12913 verbatim: *"each trajectory is generated via a stochastic mixture of student and teacher turns"*, *"regardless of which action we execute, we will query the expert action ... in every visited state."*
- **두 논문 다 SWE-bench/SWE-Gym 도메인이고 TerminalBench/Terminus를 타깃하지 않는다.** 또 "recovery-rich SFT *dataset*을 build하는 terminal data pipeline"이라기보다 turn-level interleaving IL/RL recipe다. → **terminal 도메인 + recovery-data 산출물**이 thesis의 차별 여지.
- **본문의 (R1) "on-policy data ≠ on-policy training" 위험을 보강**: 이 두 논문은 "student state + expert label"(DAgger)이라 본문이 지적한 *label은 여전히 off-policy* 한계를 공유한다. 즉 thesis가 DAgger식으로 가면 이들과, RL로 가면 본문 §3의 RL-from-own-mistakes와 경쟁하게 된다.

## B.3 Terminal 도메인 data baselines — 모두 teacher rollout only (recovery 미설계)
| 논문 | 무엇 | student rollout? | recovery/failure-matching? |
|---|---|---|---|
| **TerminalTraj** (arXiv:2602.01244, 진짜 제목 *"Large-Scale Terminal Agentic Trajectory Generation from Dockerized Environments"*; TerminalTraj=프로젝트명, ICML 2026 Spotlight) | repo→Docker→task, **50,733 verified traj**, 8 domains. TB1.0 35.30% / TB2.0 22.00% (숫자 검증 완료) | ⚠️ teacher 추정(본문 미접근, 미확인) | ❌ (success filtering 중심) |
| **On Data Engineering for Scaling LLM Terminal Capabilities** (arXiv:2602.21193) | DeepSeek-V3.2 teacher rollout + dataset adaptation + synthetic task. TB2.0 | ❌ teacher | △ 약함 — *"retaining unsuccessful trajectories ... exposing the model to realistic error states and recovery patterns"*라 언급하나 systematic 설계·분석 없음 |

→ 2602.21193의 저 한 문장은 thesis motivation을 보강하는 동시에 "남들도 어렴풋이 느끼지만 미개척"임을 보여주는 좋은 인용.

## B.4 인접 — failed trajectory 재활용 (terminal 아님)
- **AgentHER** (arXiv:2603.21357, *"Hindsight Experience **Replay** for LLM Agent Trajectory Relabeling"*): 실패 trajectory를 **HER로 goal-relabel** → SFT/DPO data (WebArena **+7.1–8.9pp** / ToolBench **+7.8–11.7pp**; 검증 시 단일 "+7.1~11.7"이 아니라 벤치별로 분리됨). 단 "fail을 다른 goal의 success로 재해석"이지 *recovery 합성*이 아니고 terminal도 아님. 본문 §3의 hindsight relabeling 행과 연결.
- **terminal-bench-rl** (github Danau5tin): GRPO로 terminal/coding RL, Qwen3 top agent. → 본문 §3 "RL from own mistakes ✅✅"의 terminal 구현 사례. thesis가 RL arm을 둘 때 직접 비교 대상.

## B.5 도메인 무대 (positioning)
- **Terminal-Bench** (arXiv:2601.11868, Stanford+Laude, 1.0=2025-05 / 2.0=2025-11, 89 task) + **Harbor** harness/task format(Claude Code·Codex CLI·OpenHands·mini-SWE-agent·Terminus 2 지원). **Terminus 2** = tmux-only neutral test-bed agent(+Opus 4.5 = TB 58%).
- 본 프로젝트의 environments_harbor가 여기서 옴 → **train(student rollout)과 deploy(TB 평가)가 동일 Harbor 환경**이라는 점이 깔끔한 fidelity 스토리(본문 §4.3 framing 보강).

## B.6 도메인 각도에서의 보완 VERDICT
- **본문 결론에 동의**하되 한 가지 추가: 본문은 Wu(2512.02389)를 최대 scoop으로 봤지만, **method 차원에서는 DAgger-LLM(2605.12913)/OEC(2512.14895)가 더 직접적 경쟁자**다. 이들은 "on-policy student rollout + teacher correction"을 *이미 LM agent에서 작동시킴*. 단 **terminal 도메인엔 아무도 안 했다** — 이게 thesis의 가장 단단한 빈 칸.
- 따라서 본문이 제시한 framing #1("Closing TermiGen's solution gap")에 **"…on TermiGen's *own* Harbor environments, head-to-head"**를 명시적으로 붙이고, DAgger-LLM/OEC를 정직히 cite하면서 *terminal 적용 + recovery-data 산출물*로 차별화하는 것이 가장 방어적이다.

### Appendix B Sources
- TermiGen html (injection mechanism): https://arxiv.org/html/2602.07274v1 / https://huggingface.co/papers/2602.07274
- Revisiting DAgger in the Era of LLM-Agents: https://arxiv.org/html/2605.12913v1
- Imitation Learning for Multi-Turn LM Agents via On-Policy Expert Corrections: https://arxiv.org/pdf/2512.14895
- TerminalTraj (Large-Scale Terminal Agentic Trajectory Generation): https://arxiv.org/abs/2602.01244 / https://github.com/multimodal-art-projection/TerminalTraj
- On Data Engineering for Scaling LLM Terminal Capabilities: https://arxiv.org/html/2602.21193v1
- AgentHER: https://arxiv.org/abs/2603.21357
- Terminal-Bench + Harbor: https://github.com/laude-institute/terminal-bench
- terminal-bench-rl (GRPO): https://github.com/Danau5tin/terminal-bench-rl

---
---

# Appendix C: 검증 로그 (2026-06-03) — deep-research adversarial-verify 크래시분 수동 재검증

> deep-research 워크플로우의 adversarial-verify 단계가 크래시해 미검증으로 남았던 출처들을 **직접 fetch해 사후 검증**. risks.md §1·§7에서 이미 검증한 11편(TermiGen, Wu, DAgger-LLM, OEC, AgentDebug, From-Correction-to-Mastery, PALADIN, Synthetic Self-Reflected, STaSC, SCoRe, START)을 제외한 나머지 9개 출처가 대상. **결론: 9개 전부 실재(지어낸 ID 없음). 단 attribution 정밀도 정정 다수, 그리고 R5 근거는 실제로 무너짐.**

| 출처 | 실재? | 핵심 claim 정확? | 정정 |
|---|---|---|---|
| 2410.15226 (synthetic diversity) | ✅ | ❌ **오인용** | 우리가 인용한 "diversity가 in-dist 일반화 안 늘림"의 **정반대**를 말함(diversity↔성능 양의 상관). distribution-matching 언급 없음. |
| 2412.02980 (Q/D/C survey) | ✅ | ⚠️ 부분 | quality→in-dist / diversity→OOD / complexity→both. *distribution-matching과 비교 안 함* → "Q/D > dist-matching" 미지지. |
| 2502.08661 (SynAlign) | ✅ | ⚠️ 역방향 | 오히려 distribution-matching이 *중요하다*는 논문. R5 framing과 결이 반대. |
| 2602.01244 (TerminalTraj) | ✅ | ✅ 숫자 정확 | 진짜 제목 "Large-Scale Terminal Agentic Trajectory Generation…"; teacher-only는 미확인(본문 미접근). ICML2026 Spotlight. |
| 2602.21193 (Data Eng for Terminal) | ✅ | ✅ verbatim 확인 | teacher=DeepSeek-V3.2 확인. 인용문 정확(생략부= "appears to provide valuable supervision,"). |
| 2603.21357 (AgentHER) | ✅ | ⚠️ 수치/제목 | "Hindsight Experience **Replay**". 수치는 WebArena +7.1–8.9 / ToolBench +7.8–11.7pp로 분리. |
| 2604.00626 (OPD survey) | ✅ | ✅ | 정정 없음. |
| 2604.13016 (Rethinking OPD) | ✅ | ⚠️ thrust 오기 | 진짜 main thrust=*thinking-pattern consistency*. 우리가 적은 "teacher-frequent context"는 실은 TM 블로그 내용. exposure-bias는 부차 동기로만 인용 가능. |
| TM blog (On-Policy Distillation) | ✅ | ✅ | "student가 teacher 자주 가는 context에서만 학습" verbatim 확인. |
| 2504.13145 (Exploring Expert Failures) | ✅ | ✅ | expert(=teacher) failure에서 학습 — student-own 아님. 정정 없음. |
| 2601.11868 (Terminal-Bench) | ✅ | ⚠️ 메타 미확인 | 89 task(TB2.0) 확인. v1.0/v2.0 날짜·"Stanford+Laude" 소속은 arXiv에서 미확인 → tbench.ai에서 별도 확인 필요. |

**가장 중요한 함의**: **R5(분포매칭 한계효용)는 literature-backed가 아니다.** 인용 3편 중 하나는 정반대, 둘은 무관 → R5는 "우리 추측"으로만 유지(§2.3 정정 반영). 나머지는 모두 실재하며 attribution 디테일만 정정.

*검증 방식: arXiv abstract + (가능 시) html 본문 직접 fetch, claim별 대조. terminal-bench v1.0/v2.0 날짜·소속만 미해결로 남김.*
