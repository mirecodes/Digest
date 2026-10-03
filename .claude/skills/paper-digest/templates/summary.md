# Summary template

A one-page digest for quick review, written after the report and condensed from it.
Same rules as the report: Korean first, then English, the same `[E#, p.N]` markers in both,
and `<!-- LANG: ... -->` markers (verify.sh checks this file too). No Sources table; it lives in the report.

```
# {Paper title}

> {Authors} · {Venue, Year} [E#, p.N]

<!-- LANG: ko -->
## TL;DR
{One sentence: problem X, idea Y, improvement Z.} [E#, p.N]

## 핵심 기여 (Contributions)
- C1 ... [E#, p.N]

## 방법 (Method)
{2-4 sentences on the key idea and architecture.} [E#, p.N]

## 주요 결과 (Results)
- {Benchmark, metric, baseline vs ours} [E#, p.N]

## 한계 (Limitations)
- {Stated by the authors} [E#, p.N]

## 코멘트 (Comments)
- [INTERP] {one or two takeaways}

<!-- LANG: en -->
{The same sections in English: TL;DR, Contributions, Method, Results, Limitations, Comments}
```
