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
