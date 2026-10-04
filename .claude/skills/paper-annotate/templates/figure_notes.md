# Figure notes template (`.work/figure_notes.md`)

One F block per entry of `.work/layout/figures.json` (figures and tables). Korean first, then English.
The first line of each language section (`요약:` / `Summary:`) is the hover popover headline (Korean ≤ 120 chars).

```
### F{n}
- figure: {figure id from figures.json, e.g. fig-p3-0}
- status: OK
#### ko
요약: {한 줄 요약}
읽는 법: {축, 범례, 기호}
- {관찰 1} [E#, p.N]
- {그래프에서 읽은 근사값} [FIG: fig-p3-0]
- {해석} [INTERP]
본문 연결: {어떤 기여(C#)·주장을 뒷받침하는지}
#### en
Summary: {one line}
How to read: {axes, legend, symbols}
- {observation 1} [E#, p.N]
- {approximate value read off the image} [FIG: fig-p3-0]
- {interpretation} [INTERP]
Link to text: {which contribution (C#) or claim it supports}
```

When the crop is wrong or unreadable:

```
### F{n}
- figure: fig-p5-1
- status: SKIP
- reason: {e.g. the box misses the legend}
```

Markers: paper text → `[E#, p.N]` (must match evidence.md); read off the image → `[FIG: <fid>]`;
computed → `[CALC: formula, E#]`; judgement → `[INTERP]`; outside knowledge → `[EXT]`.
