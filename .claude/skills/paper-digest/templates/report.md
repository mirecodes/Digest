# Report template

## Document layout

The file contains a full Korean version, then a full English version, then one shared Sources table.
The `<!-- LANG: ... -->` markers are required; verify.sh uses them.

```
# {Paper title}

> {Authors} · {Venue, Year} [E#, p.N]
> Generated: {YYYY-MM-DD} · verify: {PASS | FAIL}

<!-- LANG: ko -->
{All sections below, written in Korean}

<!-- LANG: en -->
{All sections below, written in English}

## Sources
| ID | Location | Quote |
|---|---|---|
| E1 | p.N, Abstract | "..." |
```

Headings in the Korean version use the form `## 1. 문제 정의와 동기 (Problem & Motivation)`
so that both languages share the English keyword.

## Sections (same structure in both versions)

### 0. TL;DR
One sentence: problem X, idea Y, improvement Z. [E#, p.N]

### 1. Problem & Motivation
- The problem, explained in a paragraph. [E#, p.N]
- Why existing approaches fall short (gap). [E#, p.N]

### 2. Contributions
Number the authors' stated contributions C1, C2, C3. Section 6.2 checks each one.

### 3. Background
Only the prerequisites needed to follow the paper.
Cite what the paper says; mark anything from outside the paper with `[EXT]`.

### 4. Methodology
- 4.1 Key insight
- 4.2 Overall architecture (name the main figure and its page)
- 4.3 Components: what it does, why it is needed, and the meaning of every symbol in key equations

### 5. Experimental Setup
| Item | Details | Source |
|---|---|---|
| Datasets | | [E#, p.N] |
| Baselines | | [E#, p.N] |
| Metrics | (state whether higher or lower is better) | [E#, p.N] |

### 6. Results
- 6.1 Main results

  | Benchmark | Metric | Best baseline | Ours | Δ | Source |
  |---|---|---|---|---|---|

  Write any value you compute as `[CALC: formula, E#, E#]`.
- 6.2 Claim ↔ Evidence

  | Contribution | Supporting experiment | Assessment |
  |---|---|---|
  | C1 | Table N ... [E#, p.N] | sufficient / partial / unsupported |

- 6.3 Ablation & Analysis
- 6.4 Cost (write "not reported" / "논문에 명시되지 않음" if absent)

### 7. Limitations
- Stated by the authors. [E#, p.N]
- `[INTERP]` Additional limitations you see.

### 8. Comments
Every item is your interpretation and carries `[INTERP]`.
- Novelty assessment
- What is worth borrowing (ideas, experiment design, writing)
- Open questions and reproduction pitfalls

### 9. Glossary
| Term | Meaning | Source |
|---|---|---|
