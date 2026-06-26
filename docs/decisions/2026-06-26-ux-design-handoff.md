# ADR: 디자인 핸드오프 반영 — 공통 디자인 시스템 + 배치목록/랙관리 재설계

- **Status:** Accepted
- **Date:** 2026-06-26
- **Builds on:** `2026-06-26-screen-responsibility-split.md`

## Context

외부 UX 패키지(`design_handoff_bombom_ux`: README + 6개 `*.dc.html` 프로토타입 + 화면 PNG)를
받아 기존 `web/*.html` 6화면을 그 hi-fi 디자인대로 개선했다. 프로토타입은 React 유사 런타임으로
작성됐지만, 기존 코드베이스는 **순수 HTML + fetch + DOM**이라 동일 방식(바닐라 JS)으로 포팅하고
**데이터/저장은 기존 API에 그대로 연결**했다.

## Decision

### 공통 디자인 시스템(전 화면)
- **폰트 Pretendard**(jsdelivr CDN, fallback system-ui), 숫자 `tabular-nums`.
- **캐노니컬 헤더**: 흰 sticky 헤더 + 로고 + 크럼 + nav 6개(`메인/후보풀/배치 목록/투자 리포트/
  기준정보/랙관리`). 활성 링크는 페이지마다 `class="on"`으로 하드코딩(이전의 `#cxbar` 스타일 +
  active-highlight 스크립트를 제거 — 정적 링크 리라이터와의 취약점도 같이 제거).
- **스켈레톤 로딩**: fetch 중 `.sk` shimmer → 응답 후 콘텐츠 교체("불러오는 중…" 텍스트 대체).
- **상태 색 토큰 통일**: error `#b91c1c/#fef2f2/#fecaca`, warn `#b45309/#fffbeb/#fde68a`,
  info `#1d4ed8/#eff6ff/#dbeafe`, ok `#15803d/#f0fdf4/#bbf7d0`. 카테고리/랙타입 색도 통일.

### 화면별
- **메인(home)**: 읽기전용 서브바(`● 읽기 전용 · 동기화 …` + "편집은 랙관리·PR에서") + KPI 4 +
  오퍼링→리전→존 구조(존 칩→`/placed?path=`) + 투자 3패널 + `↻ 로딩 다시 보기`.
- **후보풀(candidates)**: 툴바 `후보 N종 · 미가격 M` + 카테고리 표 + 인라인 단가(미입력 amber) +
  추가 모달.
- **배치 목록(placed) ★재설계**: 상단 **모드 토글**.
  - *태그 매핑*: 색 가진 태그 칩 사전 정의(+ 색 스와치) → "칠할 태그" 선택 → **행 클릭=브러시**로
    즉시 태깅(다중선택 일괄적용). 태그 = placement의 `release` 필드. 저장 = 랙별 `PUT /api/rack`.
  - *금액 조회·내보내기*: 태그 필터 → 행 선택 → 다크바에 **선택 합계 금액**(미가격 제외 경고) →
    **Excel(CSV, UTF-8 BOM) 클라이언트 다운로드**. 금액 = placement `unit_cost`(0/None=미가격).
- **투자 리포트(summary)**: 집계 세그 + 다크 총계바 + **미가격 경고**(`/api/health.counts.unpriced`)
  + **분포 스택바** + 표.
- **기준정보(manage)**: 통계 5칸 + 역할 안내 + 트리. **존 수준에 `🗺 배치 화면`(다크)·`⬇ draw.io`
  (외곽선) 버튼 승격**.
- **랙관리(editor) ★재설계**: **랙타입 분류 표**. 전체 랙을 랙타입별 그룹 표로 보여주고, 각 행의
  **랙타입 셀렉트**로 재분류 → 해당 그룹으로 이동. `＋ 랙 추가`는 카탈로그(`kind=rack`) 모델 검색
  모달(존·랙타입·모델·ID). 미분류/미확인 타입은 amber로 강조.

### 백엔드 추가 — `POST /api/rack/move`
랙타입 재분류는 디렉터리 모델에서 **랙 YAML을 같은 존 내 다른 rack-type 디렉터리로 이동**하는
연산이다. `scaffold.move_rack`(대상 rack-type 디렉터리 없으면 마커와 함께 생성, 충돌 시 409,
이동 후 `validate_rack` 실패하면 원위치 롤백) + 엔드포인트(이동은 old/new 경로를 함께 커밋해
삭제+추가를 한 커밋으로). 존 간 이동·서브트리 rename은 범위 밖(핸드오프 #2 "design first").

## Consequences / 데이터 모델과의 차이(의도된 적응)
- 프로토타입은 rack에 `미분류`·자유 `비고`·임의 `제거`가 있지만, bombom은 **랙이 항상 rack-type
  디렉터리 아래** 존재한다. 그래서: (a) `미분류` 그룹은 표준 4타입(compute/gpu/storage/network)에
  없는 타입이 있을 때만 표시, (b) `＋ 랙 추가`는 존+랙타입+모델을 지정해 실제 노드를 생성, (c) 행
  작업은 프로토타입의 `비고/제거` 대신 실데이터 기반 `🗺 배치`·`⧉ 복제`로 대체.
- Excel 내보내기는 서버 없이 클라이언트 Blob CSV(엑셀 호환). 정적 데모에서도 동작.
