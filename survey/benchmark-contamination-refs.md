# Benchmark contamination — sources & TermiGen data facts (2026-06-04)

Step 0+에서 student 실패 풀을 mining할 때, reward==0이 **student 실수가 아닌 경우**(채점기 버그/
flaky/timeout/불가능 task)가 섞인다. 이건 우리만의 문제가 아니라 **에이전트/코딩 벤치마크의
구조적·공인된 현상**이다. 인용 가능한 근거:

## 벤치마크에 깨진/불가능 태스크가 있다는 공인 소스

- **SWE-bench Verified** (OpenAI, 2024) — 원본 SWE-bench에 *풀 수 없는 태스크 / 잘못·약한 테스트 /
  명세 부족*이 많아서, 사람이 "명확성·테스트 정확성·풀 수 있는지"를 검수한 500개 부분집합을 따로
  공개. = 벤치마크 오염을 업계가 공식 인정하고 정제판을 낸 사례. https://www.swebench.com/verified.html
- **SWE-Bench+** (arXiv:2410.06992) — 통과 패치의 **31.08%가 약한 테스트 때문에 의심**; 그것들을
  걸러내니 해결률 12.47% → **3.97%**로 폭락. https://arxiv.org/pdf/2410.06992
- **"Are 'Solved Issues' in SWE-bench Really Solved Correctly?"** (arXiv:2503.15223) — 패치가
  테스트는 통과해도 실제론 틀린 경우 실증. https://arxiv.org/html/2503.15223v1
- **"What's in a Benchmark? SWE-Bench in APR"** (arXiv:2602.04449). https://arxiv.org/pdf/2602.04449

→ 우리 cassandra(채점기 datetime 비교 버그로 *불가능*)는 개별 사고가 아니라 이 현상의 한 사례.
   `verify_cassandra_bug.py`로 실측 증명함(8/9 통과 + valid_range만 TypeError 크래시).

## TermiGen(2602.07274) 데이터 사실 (논문 직접 확인)

- **환경(task) 단계 필터링**: 모든 task를 3지표(Environment Complexity / Data Generatability /
  **Verification Determinism**)로 채점, **>4점만 채택**(아니면 최대 3회 refinement). + Docker 빌드
  성공(최대 5회) → **"100% functionally valid environments"** 주장. → **3,500+ 환경**만 남김.
  - **즉 TermiGen도 "결정적 채점기인가 + 풀 수 있는가"로 task를 거른다** = 우리가 본 cassandra류 문제를
    막으려는 것. (그럼에도 우리 셋의 cassandra가 깨진 걸 보면 필터가 완벽하진 않음.)
- **trajectory**: **3,291개 수집 → 전부 학습 사용**(down-filter 없음). **실패도 포함**
  (Test Pass Rate ≥ 0%): *"100% pass만 남기면 쉬운 task로 편향, 복잡한 시나리오 노출을 잃는다"*.
- **3,291 < 3,500+ 인 이유**: 일부 환경이 *쓸 만한 trajectory를 아예 못 냄*(미설명 드롭). **티처가
  task를 못 풀어서가 아님** — 실패 trajectory는 그대로 포함하니까. 논문은 이 gap을 정량화 안 함.
- **teacher(generator) = Claude-4.5-Sonnet.** teacher pass-rate는 논문에 없음.

## 우리 파이프라인 수치 + 어긋남

- 수집 trial **7,473** → reward-0 **4,465** / reward-1 **3,008** → `sft_all.jsonl` = **2,302**
  (`build_dataset.py`가 reward==1만 + task별 dedupe).
- **⚠ build_dataset가 TermiGen과 어긋남**: TermiGen은 **실패 포함(≥0%)** 으로 학습하는데, 우리
  arm-①은 **`--min-reward 1.0`(성공만)**. → 우리 arm-①은 error-recovery 노출이 적은 *약화된*
  TermiGen baseline. ① vs ②½ 공정성에 영향. **충실 재현하려면 injected-error trajectory를 성공
  여부와 무관하게 포함**해야 함.
- **티처 커버리지는 현재 한계**: gpt-5.4 single-attempt라 ~2,302 고유 성공. multiple-attempt +
  더 센 teacher면 크게 늘어남 → "티처가 못 풀어 데이터 적다"는 *지금 상태*지 근본 한계 아님.
- ②½가 쓸 풀 = 저 **4,465 실패**인데, 그게 오염(verifier-bug/flaky/timeout)돼 있음 = funnel 필요 이유.
