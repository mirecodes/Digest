# Evidence: {Paper title}

Every fact in the report and summary must come from a block in this file.
verify.sh parses this file, so keep the block format exactly:

```
### E{n}
- category: {one category from the checklist below}
- page: {page number from .work/pages.md}
- loc: {Abstract | Sec 3.2 | Table 2 | Fig 4 | Eq 5 ...}
- quote: "{text copied verbatim from .work/pages.md, 1-2 sentences or one table row}"
- note: {one line in Korean: what this evidence means}
```

When the paper does not contain the information:

```
### E{n}
- category: cost
- status: NOT_REPORTED
- note: {what is missing}
```

## Checklist (categories)

- [ ] meta: title, authors, venue / year
- [ ] problem: the problem the paper addresses
- [ ] gap: why existing methods fall short (authors' claim)
- [ ] contribution: contributions stated by the authors (usually end of Introduction)
- [ ] insight: key observation or hypothesis
- [ ] method: method components (one block per component)
- [ ] background: prerequisites the paper itself mentions
- [ ] setup: datasets, baselines, metrics, implementation details
- [ ] result: main numbers (pick quotes that show baseline and metric too)
- [ ] ablation: component-removal experiments
- [ ] cost: parameters, FLOPs, latency, training cost
- [ ] limitation: limitations stated by the authors

---
