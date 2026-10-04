# 설계 결정 로그 (Paper Viewer)

계획(`docs/viewer-plan.md`)과 달라졌거나 계획이 정하지 않은 부분을 한 결정당 3–5줄로 기록한다.

---

## Phase 0

### D0-1. viewer-plan.md 위치
- 저장소 루트에 있던 `viewer-plan.md`를 `docs/viewer-plan.md`로 옮겼다. `implementation.md`와 CLAUDE.md가 모두 이 경로를 가리킨다.

### D0-2. `anthropic` 의존성은 Phase 5에 추가
- §3은 Phase 0에서 `anthropic`까지 넣으라고 하지만, 쓰는 곳은 Phase 5의 `anthropic_api` 백엔드뿐이다.
- 지금은 `fastapi`, `uvicorn[standard]`, `httpx`만 추가. `anthropic`은 Phase 5에서 optional import로 추가한다.

### D0-3. fixture의 합자·수식 글꼴
- PyMuPDF base-14 글꼴(Helvetica)은 `ﬁ`(U+FB01)를 `·`로 바꿔 버려 텍스트 레이어에 합자가 남지 않는다.
- 그래서 합자 줄과 수식 줄 `L = Σt rt (1)`만 MuPDF 내장 `cjk` 글꼴(Droid Sans Fallback)로 넣는다. 추출 시 `ﬁ`, `Σ`가 그대로 나온다.
- 이 글꼴 이름은 수학 글꼴 패턴(`CMMI|…|Symbol`)에 걸리지 않으므로, fixture의 수식 블록은 §5.2 7번의 두 번째 규칙(짧은 줄 + 줄 끝 `(n)`)으로 분류되어야 한다.

### D0-4. selftest 합성 논문을 fixtures.py로 통합
- 기존 2페이지 FooNet 생성기를 `functions/fixtures.py`의 3페이지 FooNet으로 교체했다. 기존 evidence quote(E1 p.1, E2 p.2)는 그대로 원문에 들어 있어 selftest 기대값은 바뀌지 않는다 (페이지 수 검사만 2 → 3).
- 기존 p.2 문장 앞의 `Table 2: Results on LRA.`는 뺐다. 줄 첫머리 `Table 2:`는 layout에서 캡션으로 분류되어 표 영역 감지를 교란하기 때문. E2 quote는 그 뒤 문장이라 영향 없음.
- `build_foonet()`은 정답 메타데이터(피규어/표 rect, 블록 종류 기대값, 앵커 테스트용 quote)를 반환한다.

### D0-5. textmatch 분리 범위
- `textmatch.py`에는 `loose`, `load_pages`, `find_quote_pages`만 둔다. `check_evidence`의 페이지 탐색은 원래 코드를 유지했다 (빈 quote 같은 경계 동작까지 완전히 동일하게).
- 검증: 기존 `verify.py`(HEAD)와 새 `verify.sh`의 출력이 vault의 실제 논문 9편 모두에서 바이트 단위로 같다.
- evidence 파서 이동은 실제로 재사용하는 Phase 3에서 한다.

---

## Phase 1

평가 기준: vault의 실제 논문 9편(76페이지)을 scratch에 복사해 반복 실행하고, 페이지 오버레이(블록 종류·읽기 순서·피규어 박스)를 눈으로 확인했다. 아래 규칙 변경은 모두 실제 실패 사례에서 나왔다.

### D1-1. 좌표: 회전·cropbox 실측 결과 (§4.1)
- PyMuPDF의 텍스트(`get_text`)·도형(`get_drawings`) 좌표는 **cropbox 기준이지만 회전 전(unrotated)** 공간이다. `page.rect`와 `get_pixmap(clip=)`은 회전 후 공간이다.
- 그래서 분석은 회전 전 공간에서 하고, 출력 rect만 `page.rotation_matrix`로 변환한다. `anchor.py`도 같다. pdf.js는 회전을 MuPDF와 같게 렌더하므로 일치한다.
- selftest가 90° 회전 페이지에서 앵커 rect 안의 렌더링 픽셀이 실제 글자(잉크)인지 확인한다. 회전 페이지는 단 분석을 하지 않고 `columns: 1`, 블록 `column: 0`으로 낸다 (vault 논문에는 회전 페이지 없음).

### D1-2. 캡션 판정을 §5.2보다 엄격하게
- 실제 논문에서 "Fig. 2 summarises…", "Figure 4 reports…"처럼 본문이 블록 첫 줄에서 시작하는 경우가 많다. 그래서 번호 뒤에 `.` 또는 `:`가 있어야 캡션으로 본다.
- IEEE 형식 `TABLE I`(로마 숫자, 단독 줄)도 캡션으로 인정하고 number는 정수로 변환한다. 본문 참조 정규식도 로마 숫자를 받는다.
- PyMuPDF가 부분 그림 라벨 줄 "(a) (b) (c)"와 캡션을 한 블록으로 묶는 경우가 있다. 앞 줄들이 짧은 라벨(≤ 8단어, 마침표 없음)이면 이후 줄에서 캡션이 시작되어도 인정하고, 영역 탐색에는 캡션 줄들의 상자(`cbox`)만 쓴다.

### D1-3. 그래픽 후보: clip path 반영
- matplotlib 그래프의 음영 띠는 path가 페이지 밖(x = −144)까지 뻗어 있고 축 영역 clip으로만 잘려 보인다. `get_drawings()`는 clip을 무시해서 이웃 피규어끼리 합쳐졌다.
- `get_drawings(extended=True)`의 clip(`scissor`) 스택으로 각 path rect를 잘라 쓴다. 직선(높이 0) 표 괘선이 사라지지 않도록 교집합은 tuple 연산으로 한다.

### D1-4. 피규어 영역 탐색 규칙 보정 (§5.2.1)
- 이미지·그래프 bbox가 캡션과 몇 pt 겹치는 경우가 흔하다. 그래픽 클러스터는 "중심이 캡션 쪽에 있으면" 후보로 보고, 결과 bbox는 캡션 경계에서 자른다. 텍스트 블록은 기존처럼 완전히 캡션 쪽에 있어야 한다.
- 2단 페이지에서는 왼쪽/오른쪽/걸침 그래픽을 따로 클러스터링한다. 단 사이 간격(약 14pt)이 12pt 병합 기준과 비슷해 서로 다른 단의 그림이 합쳐졌기 때문.
- 인접 클러스터 union(< 15pt)은 캡션과 x 겹침 ≥ 30%인 클러스터로 제한하고, 같은 높이대에 있는 클러스터도 합친다 (단 너비 두 개짜리 그림이 단별로 나뉜 경우).

### D1-5. 표 영역 탐색 규칙 보정
- 캡션이 표 아래에 있는 논문(예: Table II/III)이 있어서, 캡션 아래·위 양쪽을 모두 걷고 첫 행이 캡션에 더 가까운 쪽을 택한다.
- 나란히 놓인 표(Table III | Table IV)를 위해 행 블록은 캡션과 x 겹침 ≥ 30%여야 한다.
- 걷기 중단 조건에 번호 heading(`IV. EXPERIMENTAL RESULTS`)과 "줄당 8단어 초과의 여러 줄 블록"(수식·단 끊김으로 마침표 없이 끝난 본문)을 추가.
- 괘선·셀 음영 union은 반복 확장 대신 "표 텍스트 범위 ±12pt, 중심이 표 x 범위 안"인 rect만 한 번에 합친다. 반복 확장은 인라인 수식 선을 타고 페이지 아래까지 번졌다.

### D1-6. 그 밖의 결정
- header/footer 반복 규칙은 최소 2페이지에서 반복될 때만 적용 (1페이지 문서에서 모든 상단 블록이 머리글이 되는 것 방지).
- References 구간은 다음 "글꼴 기반" heading(크기 ≥ 1.1×본문 또는 bold, ≤ 2줄)에서 끝난다. 번호 패턴만으로는 끝내지 않는다 (참고문헌 항목 `1. A. Author`가 heading 정규식에 걸리므로).
- 아웃라인은 `blocks.json`의 최상위 `outline` 키에 저장한다 (§4.2 스키마에 없던 필드; viewer.json이 그대로 가져간다). TOC 항목은 같은 페이지 heading 블록과 앞 30자(공백 제거) 비교로 `block_id`를 붙인다.
- `translate/pNNN.src.md`는 번역 대상 블록이 있는 페이지만 쓴다. 그 외의 오래된 `.src.md`는 지운다. `.ko.md`는 절대 건드리지 않는다.
- `blocks.json`/`figures.json`은 diff를 보기 쉽게 들여쓰기 1로 저장한다 (키 정렬, 결정적).
- 레이아웃은 `blocks.json`이 PDF와 `figure_overrides.json`보다 새로우면 다시 계산하지 않는다 (`--force`로 강제). `blocks.json`을 마지막에 써서 중간 실패 시 재계산되게 한다.
- `papers.py`의 번역 done/total은 지금은 `.ko.md`/`.src.md`의 BLOCK 마커 수다. Phase 3에서 파서로 정확히 센다.

### D1-7. Phase 1 실측 (vault 9편)
- 캡션 기준 피규어/표 검출: captions.md의 라벨(구두점 규칙 적용) 82개 중 79개 검출. 놓친 3개는 모두 본문 문장이 줄 첫머리에 온 경우("…in Figure 8. In our…")로, 실제 캡션은 다른 페이지에서 검출됨 → 실질 누락 0. 로마 숫자 표 12개 추가 검출. low_conf(< 0.6) 0개.
- 앵커링: evidence quote 533/533 (100%), ambiguous 0.
- 속도: 논문당 0.5–1.5초 (15페이지 기준 1.4초).

---

## Phase 2

### D2-1. 프론트엔드 버전 (정확히 고정)
- React 19.3.0, Vite 8.3.2, TypeScript 7.0.2, pdfjs-dist 6.4.299, zustand 5.0.15, vitest 5.0.3, @playwright/test 1.63.0.
- §2는 React 18이라고 했지만 18에 의존하는 기능이 없고 19가 현재 버전이라 19를 썼다. TS 7(`tsc`)이 실제로 타입 오류를 잡는 것을 확인했다.
- `react-markdown`/KaTeX 등 Markdown 의존성은 AI 텍스트를 렌더하는 Phase 4/5에서 추가한다. 라우터 라이브러리는 쓰지 않는다 (라우트 2개: History API로 충분).

### D2-2. pdf.js 데이터 파일 제공 방식
- 내장되지 않은 base-14 글꼴(fixture의 Helvetica 등), CMap, wasm 디코더, ICC 파일이 필요하다. 빌드에 복사하지 않고 FastAPI가 `web/node_modules/pdfjs-dist/{standard_fonts,cmaps,wasm,iccs}`를 `/pdfjs/<kind>/<name>`으로 직접 서빙한다 (dev 모드는 Vite가 `/pdfjs`를 프록시). 이름은 정규식으로 검증.
- 전제: `web/node_modules`가 있어야 한다 (`setup.sh`가 `npm ci`로 항상 만든다).
- pdf.js 6의 text layer는 조상 요소의 CSS 변수 `--total-scale-factor`, `--scale-round-x/y`로 크기를 정한다. `pdf_viewer.css` 전체(4천 줄) 대신 `.textLayer` 규칙만 `styles.css`에 옮겼다.

### D2-3. 서버
- 출력 루트는 `PAPER_VIEWER_OUT` 환경변수가 있으면 그것을 쓴다 (selftest·e2e가 임시 루트를 쓰기 위해). 없으면 cfg.yaml의 `out_dir`.
- PDF Range 요청은 Starlette `FileResponse`가 기본 지원(206)하므로 별도 구현 없음.
- 파일 응답은 스캔으로 찾은 논문 폴더 하위만: 피규어 ID 정규식 검증 + resolve 후 폴더 안인지 확인(symlink·`..` 탈출 거부). iCloud evicted 논문은 409.
- `/crop`: bbox는 페이지 rect ±0.5pt 안이어야 하고 dpi는 36–300. 결과는 `layout/crops/<sha1>.png`에 캐시.
- `httpx` 대신 `httpx2`: Starlette 1.7의 TestClient가 `httpx` 사용을 deprecated로 경고한다.
- Library의 `[전처리]` 버튼은 job 큐(`jobs.py`)가 생기는 Phase 3에서 추가한다.

### D2-4. viewer.json (Phase 2 범위)
- layout만 묶는다: `tr`는 모두 null, `highlights` `[]`, `evidence` `{}`, `figures[].note` null. evidence 파서 공용화는 Phase 3.
- 압축 JSON(키 정렬). 신선도 검사: PDF, blocks/figures.json, report, evidence, highlights, figure_notes, overrides, `*.ko.md` 중 하나라도 더 새로우면 재빌드 (layout 자체도 먼저 최신화).
- report 헤더(`# 제목`, `> 저자 · 학회, 연도 [E#, p.N]`)에서 title/authors/venue_year를 파싱하고 인용 마커는 지운다.

### D2-5. 리더 구현 선택
- 가상화: IntersectionObserver 대신, 페이지 top을 이미 알고 있으므로 scrollTop에서 이진 탐색으로 보이는 페이지를 계산하고 ±2페이지만 canvas+text layer를 렌더한다 (결정적이고 관찰자 불필요). 범위 밖 페이지는 언마운트하며 canvas 비트맵을 즉시 해제.
- 싱크 driver 판정: §8.4 그대로(wheel/pointerdown/touchstart/keydown 후 150ms) + 포인터를 누르고 있는 동안(스크롤바 드래그)은 계속 active. `mapRef`는 첫 페이지 위·마지막 페이지 아래에서 오프셋을 그대로 옮겨 역함수 불변식이 전 구간에서 성립한다.
- 줌·창 크기·번역 패널 토글로 scale이 바뀌면 reference line 위치를 `mapRef`로 유지한다. 측정 전(폭 0) 레이아웃은 기준으로 쓰지 않는다 (처음에 2페이지로 열리던 버그의 원인).
- 번역 카드의 피규어 위치: 피규어가 캡션보다 위면 캡션 바로 앞, 아래면 바로 뒤. 캡션 없는 피규어는 같은 단에서 y가 처음으로 같거나 큰 항목 앞.
- 번역 블록 클릭 → PDF만 그 블록 중앙으로 이동 + flash. 번역 패널은 다음 사용자 스크롤 때 다시 맞춰진다 (= §8.5의 "싱크를 잠깐 멈추고 재개").
- hover 강조는 페이지 단위 selector로 구독해, 커서가 움직여도 해당 카드만 다시 그린다.
- 단축키 중 구현이 한 줄인 T/S/[/J/K//는 지금 넣었다. 나머지(H, Esc 전체, Cmd+드래그)는 해당 기능 Phase에서.

### D2-6. 성능 측정 (Phase 2 Acceptance)
- 방법: Playwright(Chromium headless, 이 Mac)에서 50페이지 합성 논문(페이지당 약 1000단어, 5페이지마다 그림)을 열고 `PerformanceObserver`로 `longtask`(> 50ms)와 `long-animation-frame`을 수집. 먼저 페이지 안에서 120ms busy loop를 실행해 관찰자가 실제로 잡는지 확인한다 (CDP `evaluate`로 돌린 busy loop는 잡히지 않아 처음 측정이 무의미했던 것을 발견하고 고침).
- 결과: PDF 패널·번역 패널 각각 처음부터 끝까지(16ms마다 300px wheel) 스크롤 시 long task 0, long animation frame 0. 별도로 초기 로딩(50장 카드 측정 포함)과 읽는 속도 스크롤(150ms마다 400px)에서도 long task 0.
- Chrome DevTools Performance 패널을 사람이 보는 수동 측정은 하지 않았다. 위 자동 측정이 `perf.spec.ts`로 매번 돈다.

### D2-7. 디자인 시스템 적용 (사용자 요청, `design.md`)
- 토큰(색·그림자·라운드), 서체 스택(Toss Product Sans → Pretendard → Apple SD Gothic Neo → Noto Sans KR), 굵기 400/600 두 가지, 버튼 7px·카드 12px, 입력창은 회색 채움 + 포커스 시 2px 파란 링, 눌림 scale(0.98)을 `styles.css`에 적용.
- 단색 파랑은 주요 동작(라이브러리 `열기`)에만 쓴다. 켜진 토글(사이드바·번역 패널·싱크)은 연한 파랑 보조 버튼, 꺼진 토글은 회색 고스트. 헤더의 이모지(🔒)는 선 아이콘으로 교체.
- 라이브러리는 design.md의 중앙 레인을 따르되 칩이 많아 480px 대신 720px로, 64px 행·헤어라인 구분선 목록으로 바꿨다.
- 리더는 원문·번역을 나란히 보는 데스크톱 도구라 모바일 우선 480px 레인은 적용하지 않고 토큰·컴포넌트만 적용했다. PDF 페이지는 문서 모양 유지를 위해 4px, 번역 카드는 12px 라운드.
- 웹 폰트는 내려받지 않는다 (로컬 전용 앱, 시스템 폰트 폴백).

---

## Phase 3

### D3-1. "아직 안 만든 것"과 "틀린 것"의 구분
- `highlights.md`/`figure_notes.md`가 없으면 검사를 건너뛴다 (오류 아님). `.ko.md`가 없는 페이지는 "미번역"으로 done/total에만 반영한다. Phase 5의 페이지 단위 번역(`translate_page`)이 부분 번역 상태를 정상으로 만들기 때문.
- 대신 존재하는 파일 안에서는 §5.5 그대로 엄격하다: `.ko.md`에 src 블록이 빠지면 ERROR, 모르는 ID ERROR, `figure_notes.md`가 있으면 모든 피규어에 F 블록이 있어야 ERROR가 없다.
- skill은 요약 줄의 `translation N/N`과 `figure notes N/N`을 완료 조건으로 확인한다. viewer.json의 `annotations_verify`는 주석 파일이 하나도 없으면 null.

### D3-2. 하이라이트 밀도 규칙의 짧은 논문 처리
- §6의 "15–40개이면서 ≤ 1.5 × 페이지 수"는 10페이지 미만 논문에서 모순이다 (예: 3페이지 → 상한 4 < 하한 15). 하한을 `min(15, 상한)`으로 둔다. 밀도는 WARN일 뿐이다.

### D3-3. evidence 파서
- `annotations.parse_evidence`를 새로 두고(loc·category·note까지 읽음) viewer 쪽은 모두 이것을 쓴다. `verify.py`의 `load_evidence`는 그대로 둔다 — digest 검증 동작을 바이트 단위로 유지하기 위해. 블록 문법은 같다.

### D3-4. 번들은 검증 결과에서 만든다
- `build_viewer`는 `verify_annotations`를 호출해 그 결과를 그대로 묶는다: 앵커링에 성공한 하이라이트, 형식이 맞는 F 블록만 들어간다. 검증과 번들이 다른 기준을 갖는 일을 막는다.
- §5.5 표 외에 추가한 WARN: 한국어 요약 120자 초과, `요약:` 줄 없음, 이유 없는 SKIP, 같은 피규어의 두 번째 F 블록(첫 번째 사용).
- golden 번들: `tests/fixtures/viewer.sample.json` (`built_at` 제외 비교). 갱신은 `scripts/internal/build_viewer.sh --update-golden`.
- fixture의 번역·하이라이트·해설 텍스트(good/bad)는 `fixtures.py`에 있다. 테스트 데이터일 뿐 논문 내용 생성이 아니다 (§14.5). e2e의 Demo 논문도 이제 주석이 붙은 상태로 준비된다.

### D3-5. skill이 쓰는 명령
- headless 세션은 `Bash(scripts/internal/*)`만 허용되므로, `layout.sh`가 폴더 경로 외에 폴더 이름·out_root 기준 상대경로도 받아 `[layout] folder: <path>`를 출력하게 했다. skill은 이 경로를 이후 단계에 쓴다.
- `scripts/annotate.sh`는 `-n` 없이 실행하면 "digest verify PASS + 주석 미완료(번역·하이라이트·피규어 해설 중 하나라도)"인 논문을 `max_papers`개까지 처리한다 (`python -m functions.papers`가 목록 제공).
- `viewer.auto_annotate: true`이면 `digest.sh`가 배치가 끝난 뒤 `annotate.sh`를 실행한다 (같은 선택 규칙이라 방금 PASS한 논문이 포함된다).

### D3-6. 전처리 job
- 동시에 1개, 나머지는 큐. 같은 폴더의 job이 대기·실행 중이면 새로 만들지 않고 그 job을 돌려준다.
- 로그는 메모리(SSE 스트림용)와 `.work/viewer/jobs/<timestamp>.log`에 남긴다. 서버 종료 시 실행 중인 프로세스를 terminate.
- `PAPER_VIEWER_ANNOTATE_CMD` 환경변수로 명령을 바꿀 수 있다. selftest와 e2e는 Claude를 부르지 않는 stub을 쓴다.

### D3-7. 실제 실행 1회 (Phase 3 Acceptance)
- 대상: vault의 `Robust Recovery Controller Quadrupedal Robot (2019)` (9페이지, 블록 172, 번역 대상 106, 피규어/표 13). 명령 `scripts/annotate.sh -n "Robust Recovery Controller Quadrupedal Robot (2019)"` (Claude Code 2.1.285, headless).
- 결과: 5분 7초, exit 0. 번역 106/106, 피규어 해설 13/13 (OK 13, SKIP 0), 하이라이트 45개(전부 evidence 유래, H 블록 0), verify_annotations PASS (ERROR 0, WARN 6 — 모두 밀도), viewer.json 생성.
- headless에서 PNG Read: 허용 플래그(`--allowedTools "Bash(scripts/internal/*)" "Read"`)로 동작했다. 해설에 이미지에서만 읽을 수 있는 내용을 `[FIG: …]`로 표시했고 SKIP이 없었다 (직접 증거는 아니고 결과로 판단).
- 품질 표본 확인: 번역은 문장 단위로 충실하고 인용 번호 `[16]`이 보존되며 glossary 용어(자세 복원, 행동 선택기 등)가 일관됨. 해설은 `[E#, p.N]`/`[FIG]`/`[INTERP]` 표시가 정확함.
- **발견:** evidence.md(57블록)의 problem/method/result 등이 자동으로 모두 하이라이트되어 45개가 된다. §6 밀도 규칙(9페이지 → 최대 13, 페이지당 4)을 evidence만으로 넘는다. skill은 evidence를 고칠 수 없으므로 WARN으로 남았다. 해결은 Phase 4(하이라이트 레이어)에서 정한다 — 후보: evidence 유래는 카테고리별 대표만 기본 표시 / 사이드바 필터로 충분 / 밀도 규칙을 H 블록에만 적용.
