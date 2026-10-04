# Translation template (`.work/translate/pNNN.ko.md`)

Copy every `<!-- BLOCK id -->` marker from `pNNN.src.md` in the same order (the `kind=` attribute may be dropped)
and put the translation under it. verify_annotations.sh parses the markers, so keep them exactly.

Source (`p003.src.md`):

```
<!-- PAGE 3 -->
<!-- BLOCK p3-b2 kind=heading -->
3.1 Problem Formulation

<!-- BLOCK p3-b3 kind=paragraph -->
We formulate the recovery task as a Markov decision process (MDP) [12]. The policy outputs joint targets at 50 Hz.
```

Translation (`p003.ko.md`):

```
<!-- BLOCK p3-b2 -->
3.1 문제 정식화 (Problem Formulation)

<!-- BLOCK p3-b3 -->
우리는 복구(recovery) 과제를 마르코프 결정 과정(Markov decision process, MDP)으로 정식화한다 [12]. 정책은 50 Hz로 관절 목표값을 출력한다.
```

Checklist per block: every sentence translated; numbers, units, symbols and `[n]` citation numbers unchanged;
first use of a term as `한국어(English)`, then the glossary term.
