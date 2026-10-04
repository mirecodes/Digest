# Highlights template (`.work/highlights.md`)

Same block grammar as evidence.md. Evidence quotes of categories problem / gap / contribution / insight /
method / result / ablation / limitation are already highlighted — add H blocks only for what they miss.

```
### H{n}
- category: {problem | contribution | insight | method | result | limitation}
- page: {page number from .work/pages.md}
- quote: "{one sentence, 40–300 characters, copied verbatim from .work/pages.md, original language}"
- note_ko: {한 줄 설명: 왜 핵심 문장인지}
- note_en: {one line in English: why it matters}
```

`note_ko` is for target_lang `ko`; for another target language use `note_<lang>` (e.g. `note_ja`).

verify_annotations.sh rejects a quote that is not on its page or cannot be anchored to the PDF, and warns when an
H quote overlaps an evidence quote on the same page.
