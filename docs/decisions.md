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
