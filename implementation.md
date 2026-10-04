# Paper Digest — Implementation

논문 PDF를 받아 **출처가 검증된** 상세 report와 1페이지 summary를 만든다 (한국어 → 영어 순).
결정적(deterministic)인 작업(이름 짓기, 파일 이동, 텍스트 추출, 인용 검증)은 Python이,
읽기·근거 수집·작성은 Claude Code의 `/paper-digest` skill이 맡는다.

핵심 원칙: **evidence first, writing second.** 원문에서 근거를 먼저 모으고 스크립트로 검증한 뒤,
검증된 근거만으로 글을 쓴다.

추가로, 처리된 논문을 **로컬 웹 리더(Paper Viewer)** 에서 읽는다: 원문 PDF ↔ 블록 단위 한국어 번역
2-pane 페이지 싱크 스크롤, 자동 하이라이트, 피규어 호버 해설, 선택/영역 설명, 논문 기반 채팅.
상세 구현 계획은 `docs/viewer-plan.md`, 진행 상태는 §8.

---

## 1. 디렉터리 구조

```
configs/cfg.yaml                 설정 (out_dir, title_words, max_papers)
requirements.txt                 pymupdf>=1.24, pyyaml>=6.0, certifi
functions/                       Python 모듈 (항상 scripts/ 경유로 실행)
  extract_pdf.py                 PDF → pages.md + captions.md
  paper_name.py                  PDF → "Short Title (Year)"
  prepare.py                     논문 선택, 폴더 생성, PDF 이동, 추출
  verify.py                      인용 검증기
  selftest.py                    합성 논문으로 파이프라인 자체 테스트
scripts/
  setup.sh                       .venv 생성 + 의존성 설치
  digest.sh [-n NAME]            headless Claude Code로 논문별 세션 실행
  internal/
    _env.sh                      (source 전용) ROOT, PY, PYTHONPATH 설정
    prepare.sh / verify.sh / selftest.sh   각 Python 모듈의 얇은 wrapper
.claude/skills/paper-digest/
  SKILL.md                       Claude가 따르는 8단계 절차 + 인용 규칙
  templates/evidence.md          evidence 블록 형식 + 카테고리 체크리스트
  templates/report.md            report 레이아웃과 섹션 0–9
  templates/summary.md           summary 레이아웃
src/                             입력 큐 (git 제외). 처리되면 PDF가 빠져나감
out/                             out_dir이 비어 있을 때 기본 출력 (git 제외)

# ---- Paper Viewer (계획: docs/viewer-plan.md §3) ----
functions/textmatch.py           loose() 등 인용 매칭 공용 함수 (verify.py에서 분리)
functions/fixtures.py            합성 논문 PDF 생성기 (selftest·e2e 공용)
functions/papers.py              out_root 스캔, paper id, 상태 조사
functions/layout.py              PDF → 블록/단/피규어 레이아웃, 피규어 crop, 번역 원본
functions/anchor.py              quote → PDF 좌표 rect
functions/annotations.py         highlights / figure_notes / 번역 파서
functions/verify_annotations.py  번역·하이라이트·피규어 해설 검증
functions/build_viewer.py        산출물 → .work/viewer.json 번들
functions/viewer/                FastAPI 서버, LLM 백엔드, 프롬프트, 내보내기
scripts/viewer.sh                리더 서버 실행
scripts/annotate.sh              headless Claude Code로 /paper-annotate 실행
.claude/skills/paper-annotate/   번역·하이라이트·피규어 해설 절차 (영어)
web/                             React + TypeScript + Vite + pdf.js 프론트엔드
tests/fixtures/                  golden viewer.json
docs/viewer-plan.md              리더 구현 계획 / docs/decisions.md 설계 결정 로그
```

출력 레이아웃 (`src/` 하위 폴더 구조가 그대로 미러링됨):

```
<out_dir>/<src 기준 하위 폴더>/<Short Title (Year)>/
  <name>.pdf
  <name> - report.md
  <name> - summary.md
  .work/pages.md       페이지 태그된 원문 (인용의 기준)
  .work/captions.md    Figure/Table 캡션 인덱스
  .work/evidence.md    근거 블록 (Claude가 작성)
  # ---- Paper Viewer ----
  <name> - notes.md                 리더에서 내보낸 Obsidian 노트 (사용자 실행 시)
  <name> - annotated.pdf            하이라이트·메모가 들어간 PDF (사용자 실행 시)
  .work/layout/blocks.json          블록·단·읽기 순서 (Python)
  .work/layout/figures.json         피규어/테이블 영역 (Python) + layout/figures/*.png
  .work/translate/pNNN.src.md       번역 원본 (Python) / pNNN.ko.md 번역 (Claude), glossary.md
  .work/highlights.md               추가 하이라이트 H 블록 (Claude)
  .work/figure_notes.md             피규어 해설 F 블록 (Claude)
  .work/viewer.json                 프론트엔드용 번들 (Python)
  .work/viewer/                     사용자 하이라이트·메모·채팅·캐시·job 로그
```

`.work/`는 점(.) 폴더라서 Obsidian이 색인하지 않는다. 출력 파일명에 논문 이름을 넣은 것도
Obsidian 검색에서 노트 이름이 겹치지 않게 하기 위함이다.

---

## 2. 설정 — `configs/cfg.yaml`

| 키 | 의미 | 기본 |
|---|---|---|
| `out_dir` | 출력 루트. 절대경로, `~`, 프로젝트 기준 상대경로 모두 가능 | 비어 있으면 `<project>/out` |
| `target_lang` | 리더 번역·피규어 해설·하이라이트 메모의 언어 (ISO 639-1). 파일이 언어별로 따로 저장됨 (`pNNN.<lang>.md`) | `ko` |
| `title_words` | 긴 제목에서 남길 단어 수 (stopword 제외) | 5 |
| `max_papers` | `-n` 없이 실행할 때 한 번에 처리할 최대 논문 수. 0/빈 값 = 무제한 | — |

현재 `out_dir`은 iCloud의 Obsidian vault(`Uru Vault/Paper Digest`)를 가리킨다.
digest 보고서/요약은 `target_lang`과 무관하게 한국어 → 영어 그대로다 (verify.py의 ko/en 구간 검사).

`viewer:` 하위 키(host, port, llm_backend, model_*, auto_annotate 등)는
`docs/viewer-plan.md` §11 참고. 키가 없어도 기본값으로 동작한다.

---

## 3. 전체 파이프라인

```
src/*.pdf
   │  scripts/digest.sh  (또는 Claude Code에서 /paper-digest)
   ▼
[1] Prepare        prepare.sh → 레지스트리로 중복 확인 → 이름 결정 → 폴더 생성 → 추출 → PDF 복사 (src/는 그대로)  (Python)
[2] Read           .work/pages.md 전체를 처음부터 끝까지 읽음                 (Claude)
[3] Evidence       .work/evidence.md 작성 (원문 그대로 인용)                  (Claude)
[4] Verify E       verify.sh --evidence-only, ERROR 0개까지 수정             (Python ↔ Claude)
[5] Report         "<name> - report.md" (한국어 전체 → 영어 전체 → Sources)   (Claude)
[6] Summary        "<name> - summary.md" (report를 1페이지로 압축)           (Claude)
[7] Verify all     verify.sh, ERROR 수정 (최대 3회), WARN 처리               (Python ↔ Claude)
[8] Report back    폴더, PASS/FAIL, 경고 수, NOT_REPORTED, 표 파싱 불확실 항목
```

리더용 후처리 (별도 명령 `scripts/annotate.sh` / `/paper-annotate`, `viewer.auto_annotate: true`면 digest 뒤 자동):

```
[A1] Layout        layout.sh → blocks.json, figures.json, figure crops, translate/*.src.md   (Python)
[A2] Translate     glossary.md → 페이지별 pNNN.<target_lang>.md                             (Claude)
[A3] Highlights    highlights.md (evidence가 못 다룬 핵심 문장만)                            (Claude)
[A4] Figure notes  피규어 PNG를 보고 figure_notes.md (한→영)                                (Claude)
[A5] Verify        verify_annotations.sh, ERROR 수정 (최대 3회)                             (Python ↔ Claude)
[A6] Build         build_viewer.sh → .work/viewer.json                                      (Python)
```

### 3.1 진입점

| 위치 | 전체 src/ (최대 `max_papers`) | 논문 하나 |
|---|---|---|
| Claude Code | `/paper-digest` | `/paper-digest -n NAME` |
| 터미널 | `scripts/digest.sh` | `scripts/digest.sh -n NAME` |

`NAME`은 src/ 기준 상대경로, 파일명, stem(확장자 제외), 또는 임의의 PDF 경로.

| 위치 | 리더용 후처리 | 리더 |
|---|---|---|
| Claude Code | `/paper-annotate -n NAME` | — |
| 터미널 | `scripts/annotate.sh [-n NAME]` (NAME = 출력 폴더 경로 또는 폴더 이름) | `scripts/viewer.sh` → http://127.0.0.1:8765 |

### 3.2 `scripts/digest.sh` (배치 실행기)

1. `prepare --list [-n NAME]`로 처리할 논문 목록을 얻는다 (아무 것도 없으면 exit 1로 종료).
2. `out_root()`로 출력 루트를 구해 `mkdir -p`.
3. 논문마다 **독립된 headless 세션**을 띄운다:
   ```
   claude -p "/paper-digest -n \"$PAPER\"" \
     --add-dir "$OUT" --permission-mode acceptEdits \
     --allowedTools "Bash(scripts/internal/*)" < /dev/null
   ```
   - `--add-dir`: 프로젝트 밖(vault)의 출력 폴더에 쓰기 허용
   - `--allowedTools`: Bash는 `scripts/internal/*`만 허용
   - `< /dev/null`: claude가 while 루프의 논문 목록 stdin을 먹지 않도록
4. 실패한 세션 수를 세고, 하나라도 실패하면 exit 1.

---

## 4. Python 모듈 상세

모든 모듈은 `scripts/internal/*.sh` → `_env.sh`를 통해 `.venv` Python으로 실행된다.
`_env.sh`는 `ROOT`를 구하고, `.venv/bin/python`(또는 Windows `Scripts/python.exe`)을 `PY`로 잡고,
`PYTHONPATH`에 `ROOT`를 추가해 `functions` 패키지를 import 가능하게 한다. `.venv`가 없으면 에러.

### 4.1 `functions/extract_pdf.py`

`extract(pdf_path, out_dir) -> dict`

- PyMuPDF로 페이지마다 `get_text("text")`.
- `pages.md`: 페이지마다
  ```
  <!-- PAGE N -->
  # [p.N]

  <text>
  ```
  HTML 주석이 기계용 마커, heading은 사람용. **이후 모든 페이지 번호는 이 마커 기준**
  (PDF에 인쇄된 번호가 아님).
- `captions.md`: 각 줄에서 `Table|Tab.|Figure|Fig. <숫자>`로 시작하는 캡션을 찾아
  `- p.N: <캡션 앞 200자>`로 기록.
- 반환: `pages`, `chars`, `captions`, `scanned`, `out_dir`.
  `scanned`는 페이지당 평균 글자 수 < 200 (`MIN_CHARS_PER_PAGE`)이면 True.
- 단독 실행: `python -m functions.extract_pdf <pdf> [out_dir]` (기본 `<pdf dir>/.work`),
  스캔본이면 exit 2.

### 4.2 `functions/paper_name.py`

`paper_name(pdf, title_words=5, offline=False) -> (name, source)`

메타데이터 조회 순서 (`resolve`):

1. **arXiv ID** — 파일명(`2301.12345v2`, `arxiv_…`, 구형 `hep-th/9901001` 또는 `_` 구분) →
   arXiv DOI(`10.48550/arxiv.…`) → 앞 2페이지 본문의 `arXiv:` 표기 순으로 탐색 → arXiv API.
   API 호출 간 3초 간격 유지 (`ARXIV_DELAY`).
2. **DOI** — 파일명(`10.`로 시작, 첫 `_`를 `/`로 복원) → PDF 메타데이터 `subject`/`keywords` →
   본문 순 → Crossref API. 제목에 subtitle이 있으면 `Title: Subtitle`로 합침.
   연도는 `issued` → `published-print` → `published-online` → `created` 순.
3. **PDF 내장 메타데이터** — `title`, `creationDate`의 연도. `Microsoft Word - …`, `.docx`,
   `untitled` 같은 쓰레기 제목은 무시.
4. 전부 실패하면 원래 파일 stem 유지.

`offline=True`면 1·2의 네트워크 호출을 건너뛴다. 네트워크 실패는 stderr에 로그만 남기고 다음 단계로.
SSL은 `certifi` CA 번들 사용 (python.org macOS 빌드 대응). 타임아웃 20초.

이름 포맷 (`format_name`):
- 제목 단어 수가 `title_words` 이하이면 그대로.
- 초과하면 stopword(`a, the, of, for, using, …`)를 뺀 앞 `title_words` 단어만 남김 (Better BibTeX shorttitle 방식).
- 연도가 있으면 `Title (Year)`.
- `valid_filename`: NFC 정규화, `\/?*:|"<>` 제거, 제어문자 제거, 공백 정리, 앞의 `.` 제거 (Zotero 규칙).

예: `Robust Recovery Controller for a Quadrupedal Robot using Deep Reinforcement Learning` (2019)
→ `Robust Recovery Controller Quadrupedal Robot (2019)`

### 4.3 `functions/prepare.py`

CLI: `prepare.sh [-n NAME] [--list] [--force] [--dry-run] [--offline]`

**선택 (`select`)**
- `-n NAME`: 실제 존재하는 경로면 그 파일. 아니면 src/ 아래 PDF 중 상대경로 / 파일명 / stem /
  확장자 뺀 상대경로가 일치하는 것. 2개 이상 매치되면 에러(exit 1).
- `-n` 없음: src/ 아래 모든 PDF(확장자 대소문자 무관)를 정렬해 앞에서 `max_papers`개.
- `--list`: 선택 결과만 출력하고 종료 (digest.sh가 사용).

**`prepare_one`**
1. `paper_name()`으로 이름 결정, `target_dir()`로 출력 폴더 계산
   (src/ 안의 PDF는 하위 폴더를 미러링, 밖의 PDF는 출력 루트 바로 아래).
2. `--dry-run`: 이름과 폴더만 출력.
3. 폴더가 이미 있고 `--force`가 없으면 `skip (folder exists …)` → 코드 3.
4. `extract()`로 `.work/pages.md`, `.work/captions.md` 생성.
5. 스캔본이면: 새로 만든 폴더는 삭제, PDF는 src/에 그대로 둠 → 코드 2 (OCR 후 재시도 가능).
6. PDF를 `<name>.pdf`로 **이동**(src/ 안) 또는 **복사**(src/ 밖).
7. `[prepare] ready: <folder>` 출력 — skill은 이 줄을 보고 다음 단계로 간다.

**Exit codes**
| 상황 | 코드 |
|---|---|
| 정상 / 배치 실행 (일부 skip 포함) | 0 |
| 선택된 PDF 없음, `-n` 매치 다수 | 1 |
| `-n` 단건: 스캔본 | 2 |
| `-n` 단건: 폴더 이미 존재 | 3 |

배치 모드에서는 skip된 논문이 있어도 0을 반환하고 `N/M ready`만 출력한다.

### 4.4 `functions/verify.py`

CLI: `verify.sh "<paper folder>" [--evidence-only]` — ERROR가 하나라도 있으면 exit 1.

**텍스트 정규화 (`loose`)**: NFKC → 소문자 → `[0-9a-z가-힣]` 외 전부 제거.
줄바꿈, 하이픈 분리, 공백, 기호 차이가 인용 매칭에 영향을 주지 않는다.

**evidence 파싱**: `### E<n>` 블록마다 `- page:`, `- quote: "…"`, `- status: NOT_REPORTED`를 읽는다.

**검사 1 — evidence ↔ pages.md** (`check_evidence`)
| 조건 | 결과 |
|---|---|
| evidence 블록이 하나도 없음 | ERROR |
| NOT_REPORTED가 아닌데 page/quote 누락 | ERROR |
| 정규화된 quote가 15자 미만 | WARN (신뢰도 낮음) |
| 명시한 페이지에는 없고 다른 페이지에 있음 | ERROR `not on p.X; actually on p.[Y]` |
| 어느 페이지에도 없음 | ERROR `quote not found` (지어냈거나 의역) |

**검사 2 — report/summary** (`check_output`, `--evidence-only`면 생략)
대상: `<folder>/<folder name> - report.md`, `… - summary.md`.

줄 단위로 읽으며 `<!-- LANG: ko|en -->` 마커로 현재 언어를, heading으로 exempt 여부를 추적한다.
heading에 `comment / discussion / sources / 코멘트 / 토론 / 출처`가 있으면 그 섹션은 숫자 검사 면제.

| 조건 | 결과 |
|---|---|
| 파일 없음 | ERROR |
| `[E#…]`가 존재하지 않는 evidence를 가리킴 | ERROR |
| `[E#, p.N]`의 N이 evidence의 page와 다름 | ERROR |
| NOT_REPORTED evidence를 인용 | WARN ("not reported"라고 쓰였는지 확인) |
| `ko` 또는 `en` 마커 누락 | ERROR |
| 한국어/영어가 인용한 evidence ID 집합이 다름 | ERROR |
| 한국어/영어에 등장하는 소수 집합이 다름 | WARN |
| 숫자(소수, `%`, `x`, `×`, `pp`, `%p`)가 있는데 인용·`[CALC:]`·`[INTERP]`·`[EXT]`가 없음 (면제 섹션 제외) | WARN |

반환: `verify_paper(paper_dir, evidence_only) -> (errors, warnings, evidence_count)`.

### 4.5 `functions/selftest.py`

`scripts/internal/selftest.sh` → `[selftest] PASS|FAIL`. `functions/` 변경 후 반드시 통과해야 함.

- **naming**: 긴 제목 축약, 특수문자 제거, arXiv ID 추출(파일명/본문), `target_dir` 미러링, `output_path` 형식.
- **selection**: 임시 src/에서 전체 선택, `max_papers` 제한, stem/상대경로 매칭, 매치 없음, `.txt` 무시, `.PDF` 대문자 확장자.
- **extract + verify**: PyMuPDF로 2페이지짜리 합성 논문(FooNet)을 만들어
  - good case: evidence + report/summary가 ERROR 없이 통과해야 함
  - bad case: 페이지 틀림, 없는 quote, 없는 E9 인용, 한/영 인용 불일치 → 각각 ERROR,
    출처 없는 숫자 → WARN이 나와야 함

---

## 5. Claude 측 규칙 (`.claude/skills/paper-digest/`)

### 5.1 Evidence 블록 형식

```
### E{n}
- category: {meta|problem|gap|contribution|insight|method|background|setup|result|ablation|cost|limitation}
- page: {pages.md 기준 페이지}
- loc: {Abstract | Sec 3.2 | Table 2 | Fig 4 | Eq 5 ...}
- quote: "{pages.md에서 그대로 복사, 1–2문장 또는 표 한 행, 원문 언어}"
- note: {한국어 한 줄 설명}
```
정보가 없으면 `- status: NOT_REPORTED` 블록으로 남긴다. 모든 카테고리를 다뤄야 한다.
표 행/열 매핑이 불확실하면 note에 `table parsing uncertain`.

### 5.2 인용 마커

| 내용 | 마커 | 허용 위치 |
|---|---|---|
| 논문의 사실·수치·주장 | `[E#, p.N]` | 어디든 |
| 인용된 수치로 계산한 값 (반올림·단위 변환 포함) | `[CALC: 식, E#, E#]` | 어디든 |
| 논문 밖 일반 지식 | `[EXT]` | Background, Comments |
| 본인의 평가·추론 | `[INTERP]` | Limitations, Comments, Discussion |

- 수치는 evidence quote와 **정확히** 일치해야 한다. 다른 논문 수치를 기억으로 쓰지 않는다.
- "SOTA", "significant" 같은 평가어는 저자 인용이거나 `[INTERP]`.
- 확실하지 않으면 빼고 "논문에 명시되지 않음"으로 쓴다.

### 5.3 Report 구조

```
# {Title}
> {Authors} · {Venue, Year} [E#, p.N]
> Generated: YYYY-MM-DD · verify: PASS|FAIL
<!-- LANG: ko -->   한국어 전체 (heading 예: ## 1. 문제 정의와 동기 (Problem & Motivation))
<!-- LANG: en -->   영어 전체 (한국어판의 충실한 번역: 같은 섹션, 같은 evidence ID, 같은 수치)
## Sources          실제 인용한 evidence만 담은 공용 표
```
섹션: 0 TL;DR · 1 Problem & Motivation · 2 Contributions (C1, C2…) · 3 Background ·
4 Methodology (insight / architecture / components, 수식의 모든 기호 설명) · 5 Experimental Setup ·
6 Results (main / Claim↔Evidence / Ablation / Cost) · 7 Limitations · 8 Comments (전부 `[INTERP]`) · 9 Glossary.

### 5.4 Summary 구조

같은 규칙(한→영, 같은 마커, LANG 마커)에 TL;DR · Contributions · Method · Results · Limitations · Comments.
Sources 표 없음. 새 사실 금지 — 모든 인용이 report에 이미 있어야 한다.

### 5.5 예외 처리 (skill)

| prepare 결과 | 대응 |
|---|---|
| exit 3 (폴더 존재) | 대화형: 사용자에게 물은 뒤 `--force`. headless(`claude -p`): `--force` 금지, 보고만 |
| exit 2 (스캔본) | PDF는 src/에 남음, OCR 필요하다고 안내 |
| exit 1 | 처리할 것 없음, 중단 |
| verify ERROR가 3회 수정 후에도 남음 | 그대로 사용자에게 보고 |

---

## 6. 설치와 운영

```bash
scripts/setup.sh                     # .venv + requirements (PYTHON_BIN=python3.12 로 인터프리터 선택)
scripts/internal/selftest.sh         # [selftest] PASS 확인
scripts/internal/prepare.sh --dry-run [-n NAME]   # 이름만 미리보기, 아무것도 이동 안 함
scripts/digest.sh [-n NAME]          # 실행
scripts/internal/verify.sh "<paper folder>"       # 수정 후 재검증

# Paper Viewer (구현 후)
scripts/setup.sh --with-e2e          # + web 빌드(Node ≥ 20), Playwright 브라우저
scripts/annotate.sh [-n NAME]        # 번역·하이라이트·피규어 해설 생성 + 검증 + 번들
scripts/viewer.sh [--dev]            # 리더 실행
scripts/internal/viewer_test.sh [--e2e]
```

프로젝트 규칙 (CLAUDE.md):
- Python은 항상 `scripts/` 경유 (`.venv`). 새 의존성은 `requirements.txt` → `setup.sh`.
- `functions/`, `scripts/`, `.claude/`, CLAUDE.md는 영어로 작성.
- 논문 사실은 `.work/evidence.md`에서만. 인용은 원문 언어 그대로.
- `verify.sh`에 ERROR가 남아 있으면 digest는 미완료.
- 리더 관련 규칙은 `docs/viewer-plan.md` §14 (CLAUDE.md 추가 문구 포함).

---

## 7. 알려진 한계

- **스캔본 PDF**: 텍스트 레이어가 없으면 처리하지 않음 (OCR은 파이프라인 밖).
- **표 추출**: PyMuPDF `text` 모드라 표의 행/열이 섞일 수 있음 → evidence note로 표시만 함.
- **인용 매칭 정규화**: `loose()`는 `0-9a-z가-힣`만 남기므로 그리스 문자, 악센트 문자, 수식 기호,
  한·영 외 문자는 비교에서 사라진다. 이런 문자만 다른 인용은 구분하지 못함.
- **숫자 검사는 WARN**: 출처 없는 숫자, 한/영 소수 불일치는 경고일 뿐 실패시키지 않는다.
  또한 한/영 비교는 소수(`61.4` 같은)만 대상.
- **이름 충돌**: 서로 다른 논문이 같은 `Short Title (Year)`가 되면 두 번째는 `folder exists`로 skip.
- **배치 prepare exit code**: skip이 있어도 0이므로 skip 여부는 출력 로그로 판단해야 한다.
- **arXiv 속도 제한**: 호출 간 3초 대기 → 배치가 클수록 prepare가 느려짐.
- 리더 쪽 예상 한계는 `docs/viewer-plan.md` §15.

---

## 8. Paper Viewer — 진행 상태

> coding agent가 Phase를 끝낼 때마다 이 표와 아래 as-built 메모를 갱신한다. 계획과 달라진 점은 `docs/decisions.md`.

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | textmatch 분리, 합성 fixture, 의존성·setup | done |
| 1 | layout (블록·단·읽기 순서·피규어 영역), anchor | done |
| 2 | FastAPI 서버, 라이브러리, 2-pane 리더, **페이지 싱크 스크롤**, 블록 링크 | done |
| 3 | `/paper-annotate` skill, verify_annotations, viewer.json 번들, 전처리 job | done |
| 3.5 | 논문 레지스트리(중복 방지, src/ 보존), 단계별 실행 드롭다운, 영어 UI, `target_lang` | done |
| 4 | 자동 하이라이트 레이어, **피규어 호버 해설 popover**, bbox 수정 | planned |
| 5 | LLM 백엔드, 선택/영역 설명, 선택·페이지 번역, 채팅, grounding 배지 | planned |
| 6 | 사용자 하이라이트·메모, notes.md / annotated.pdf 내보내기 | planned |
| 7 | 참고문헌 미리보기, 다크 모드, 단축키, 정밀 싱크, 성능 | planned |

### As-built 메모

**Phase 0**
- `functions/textmatch.py`: `loose`, `load_pages`, `find_quote_pages`. `verify.py`가 import (출력은 리팩터 전과 동일 — vault 논문 9편으로 확인).
- `functions/fixtures.py`: `build_foonet(pdf) -> truth`. 3페이지 합성 논문 + 정답 메타데이터. selftest가 사용.
- `requirements.txt`: + fastapi, uvicorn[standard], httpx (`anthropic`은 Phase 5).
- `scripts/setup.sh [--with-e2e]`: `web/package.json`이 있고 Node ≥ 20이면 `npm ci && npm run build`, 없으면 경고만. 반복 실행 안전.

**Phase 1**
- `scripts/internal/layout.sh "<paper folder>" [--force]` → `.work/layout/blocks.json`, `figures.json`, `figures/<fid>.png`, `.work/translate/pNNN.src.md`. 최신이면 건너뜀 (`(up to date)`).
- `scripts/internal/anchor_check.sh "<paper folder>"` → evidence quote 앵커링 성공률.
- `functions/papers.py`: `scan()`, `paper_id()`, `resolve_for_annotate()`, `viewer_cfg()`(cfg.yaml `viewer:` + 기본값).
- 실측(vault 9편): 피규어/표 캡션 검출 실질 누락 0, low_conf 0, 앵커링 533/533 (100%). 논문당 0.5–1.5초.
  상세와 휴리스틱 보정 내역은 `docs/decisions.md` Phase 1.
- 수동 확인: vault의 `Robust Recovery Controller Quadrupedal Robot (2019)`에 실제 실행함 (`pages=9 blocks=172 figures=13 low_conf=0`).

**Phase 2**
- `scripts/viewer.sh [--dev] [--port N] [--no-open]` → http://127.0.0.1:8765. 라이브러리 → `열기` → 리더 (`/r/<id>?page=N` 딥링크).
- `scripts/internal/build_viewer.sh "<paper folder>"` → `.work/viewer.json` (서버는 요청 시 stale이면 자동 재빌드).
- `scripts/internal/viewer_test.sh [--e2e]`: vitest 16개 + (`--e2e`) 빌드 → 임시 out_root에 합성 논문 2편(`python -m functions.fixtures <root>`) → Playwright 5개 (§12.3의 1–3, 9 + 50페이지 성능).
- 리더: PDF(가상화, 선택 가능한 text layer) | 번역 카드(번역 없으면 원문 회색 이탤릭, 피규어·수식은 이미지) — 페이지 싱크(🔒/`S`), 블록 hover 상호 강조, 번역 블록 클릭 → PDF 이동, PDF `Alt+클릭` → 번역 이동, 페이지 표시기 클릭 → 이동, 줌(−/+/맞춤), 아웃라인, 블록 검색(`/`), 패널 비율 드래그. 단축키 T/S/[/J/K//.
- 실측: 50페이지 스크롤 시 long task 0, long animation frame 0 (두 패널 모두, 측정 방법은 decisions.md D2-6).
- 수동 확인 절차: `scripts/setup.sh` → `scripts/viewer.sh` → 라이브러리에서 논문 열기 → 왼쪽을 스크롤하면 오른쪽 카드가 같은 페이지 위치로 따라오는지, 싱크 버튼을 끄면 멈추는지, 오른쪽 블록에 올리면 왼쪽에 파란 외곽선이 뜨는지 확인. 번역이 없는 논문은 오른쪽이 원문 회색 표시.
- 디자인: `design.md` 토큰·컴포넌트 적용 (decisions.md D2-7).

**Phase 3**
- 실행 절차 (실제 논문 하나):
  1. `scripts/annotate.sh -n "<폴더 이름>"` — headless Claude Code가 `/paper-annotate`를 실행 (glossary → 페이지별 `pNNN.ko.md` → `highlights.md` → `figure_notes.md` → verify → `viewer.json`). `-n` 없이 실행하면 digest PASS이면서 주석이 미완료인 논문을 `max_papers`개까지.
     또는 라이브러리의 `전처리` 버튼 (같은 스크립트를 job으로 실행, 로그가 행 아래에 실시간 표시).
  2. 확인: `scripts/internal/verify_annotations.sh "<폴더>"` → `translation N/N`, `figure notes N/N`, `PASS`.
  3. `scripts/viewer.sh`로 열어 오른쪽에 한국어 번역이 나오는지 확인.
- 실측 (vault `Robust Recovery Controller Quadrupedal Robot (2019)`): 5분 7초, 번역 106/106, 하이라이트 45 (evidence 유래), 피규어 해설 13/13, verify PASS (밀도 WARN 6). decisions.md D3-7.
- 새 명령: `scripts/internal/verify_annotations.sh "<폴더>" [--translation] [--highlights] [--figures]`, `scripts/internal/build_viewer.sh --update-golden`.
- `scripts/internal/layout.sh`는 폴더 이름도 받는다. `viewer.auto_annotate: true`면 `digest.sh`가 끝에 `annotate.sh`를 실행.
- 테스트: selftest(+ verify_annotations good/bad, golden 번들, job SSE) / vitest 16 / Playwright 7 (전처리 버튼 stub, 번역 표시 추가).

**Phase 3.5 — 논문 관리 재구성** (decisions.md D3.5-*)
- `src/`는 더 이상 비워지지 않는다. prepare가 PDF를 출력 폴더로 **복사**한다.
- 레지스트리 `<out_dir>/.paper-registry.yaml` (`functions/registry.py`): PDF 내용 해시(SHA-256 앞 16자)를 키로 src/ 경로·출력 폴더·상태(new/prepared/digested/annotated)·digest·번역·하이라이트·해설 수를 한 파일에 기록. 디스크에서 다시 만들 수 있는 캐시라 지워도 된다. `python -m functions.registry`(스크립트 경유)로 표 출력.
  - `digest.sh`(인자 없음)는 출력 폴더가 없는 src/ PDF만 처리. 같은 PDF가 이름만 바뀌어도 건너뜀.
  - prepare: 이미 digest PASS → `skip (already digested)`, exit 4. 폴더는 있는데 digest가 없거나 FAIL → 재추출 없이 `ready`(이어서 진행).
- 라이브러리: 출력 폴더 + 아직 처리 안 된 src/ PDF(`New`)를 함께 보여준다. `Process ▾` 드롭다운: Run all / Summary & report / Translation / Highlights / Figure notes. 끝난 단계는 체크 표시, 불가능한 단계는 비활성(이유는 툴팁).
  - API: `POST /api/papers/{id}/run {"action": ...}` (기존 `/annotate` 대체). Run all = (digest가 PASS가 아니면) digest → 남은 주석 단계 전부.
  - `scripts/annotate.sh -n NAME --only translation,highlights,figures`. `--only` 없으면 skill이 이미 완료된 부분은 건너뜀.
- UI는 영어만. 번역 언어는 `configs/cfg.yaml`의 `target_lang` (기본 `ko`). viewer.json의 언어 의존 키는 `tr`/`note_tr` + 최상위 `lang`.
- "Method Not Allowed" 원인: Phase 3 이전에 띄운 서버(`--reload` 없음)가 계속 떠 있어 POST 라우트가 없었다. 서버를 재시작하면 해결. 이제 클라이언트가 405를 "서버가 오래됨, 재시작" 메시지로 보여준다.
- 테스트: selftest(+ 레지스트리·prepare 복사/이어하기/중복, run API) / vitest 16 / Playwright 8.
- AI 백엔드 선택 (D3.5-6): `configs/cfg.yaml`의 `agent.backend: claude | codex | gemini`, `agent.model` (빈 값 = CLI 기본). 모든 AI 실행은 `scripts/internal/agent.sh`를 거친다 (`--check` 로그인 확인, `--dry-run` 명령 확인). 한 번만 바꿔 쓰기: `PAPER_AGENT=gemini scripts/digest.sh`. 사용자 가이드는 `README.md`.

