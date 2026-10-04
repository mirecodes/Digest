# Highlights template (`.work/highlights.md`)

The paper's reading map: 8–24 big-picture key sentences, each with a one-line summary note. Evidence quotes
(evidence.md) are an internal record for the report and are never highlighted.

```
### H{n}
- category: {problem | prior_work | contribution | method | result | assumption | insight | limitation}
- page: {page number from .work/pages.md}
- quote: "{one sentence, 40–300 characters, copied verbatim from .work/pages.md, original language}"
- note_ko: {역할: 한 줄 요약, e.g. "풀려는 문제: 낙상 후 복구 동작을 하나의 정책으로 학습하기 어렵다"}
- note_en: {Role: one-line summary, e.g. "Problem: one policy struggles to learn fall recovery"}
```

Write the blocks in reading order: problem → prior_work → assumption → contribution → method → result → insight →
limitation. `note_ko` is for target_lang `ko`; for another target language use `note_<lang>` (e.g. `note_ja`).

Example (FooNet):

```
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
```

verify_annotations.sh rejects a quote that is not on its page or cannot be anchored to the PDF, and warns when a
core category (problem, prior_work, contribution, method, result) is missing, a note is missing, or the count is
outside 8–24.
