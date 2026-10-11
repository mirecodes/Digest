# Highlights template (`.work/highlights.md`)

The paper's reading map: the plan (`## Reading map`, ignored by the viewer), then 8–24 H blocks, one or two per map
line, each a verbatim key sentence with a one-line note. Evidence quotes (evidence.md) are an internal record for the
report and are never highlighted.

```
## Reading map
- Thesis: {the main claim in one sentence}
- Problem: {the task and why it matters}
- Gap: {what existing work does and the shortcoming this paper attacks}
- C1: {contribution} | how: {mechanism} | shown by: {experiment or number}
- C2: …
- Scope: {assumptions / settings}            (omit if none)
- Insight: {why it works / takeaway}
- Limits: {stated limitations}               (omit if none)

### H{n}
- category: {problem | prior_work | assumption | contribution | method | result | insight | limitation}
- claim: {C# — only for contribution, method and result}
- page: {page number from .work/pages.md}
- quote: "{one sentence, 40–300 characters, copied verbatim from .work/pages.md, original language}"
- note_ko: {역할: 한 줄 요약, e.g. "핵심 방법 (기여 1): 상태-행동 이력으로 환경 특성을 추정한다"}
- note_en: {Role: one-line summary, e.g. "Method (C1): estimates the environment from the state-action history"}
```

Write the blocks in map order: problem → prior_work → assumption → C1 (contribution, method, result) → C2 … →
insight → limitation. `note_ko` is for target_lang `ko`; for another target language use `note_<lang>` (e.g.
`note_ja`).

Example (FooNet):

```
## Reading map
- Thesis: FooNet makes long-context modeling linear by routing each token to a few keys instead of all of them
- Problem: long-context modeling is limited by attention's quadratic cost
- Gap: dense attention compares every pair of tokens
- C1: a learned router for sparse attention | how: the router picks the keys each token attends to | shown by: accuracy vs. dense attention at a fraction of the cost
- Insight: most attention mass falls on a few keys, so routing loses little
- Limits: the router adds training instability on short sequences

### H1
- category: problem
- page: 1
- quote: "Existing methods scale quadratically with sequence length, which limits long-context modeling."
- note_ko: 풀려는 문제: 기존 방법은 입력 길이에 대해 이차 복잡도라 긴 문맥을 다루기 어렵다
- note_en: Problem: existing methods are quadratic in length, which limits long contexts

### H2
- category: prior_work
- page: 1
- quote: "Dense attention compares every token with every other token"
- note_ko: 기존 방법의 한계: dense attention은 모든 토큰 쌍을 비교한다
- note_en: Prior work: dense attention compares every pair of tokens

### H3
- category: contribution
- claim: C1
- page: 1
- quote: "We propose FooNet, which learns a router that selects the keys each token attends to."
- note_ko: 기여 1: 토큰마다 볼 key를 고르는 router를 학습하는 FooNet
- note_en: Contribution 1: FooNet learns a router that picks the keys each token attends to
```

verify_annotations.sh rejects a quote that is not on its page or cannot be anchored to the PDF, and warns when a
core category (problem, prior_work, contribution, method, result) is missing, a claim C# lacks its contribution,
method or result highlight, a note is missing, or the count is outside 8–24.
