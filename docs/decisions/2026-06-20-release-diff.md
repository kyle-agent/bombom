# 2026-06-20 — 릴리즈 변경 비교(ref-to-ref diff): 확정 태그 간 설계 델타

## Context
"릴리즈"는 단어 그대로의 출시가 아니라 **설계들의 모음을 확정한 스냅샷**이다(사용자 정의). 확정은
annotated git 태그(태그명 = confirmation id)로 봉인된다(ADR confirm-workflow). 디자이너의 실제
요구인 **장비 교체·제거(decommission) 가시성**은 곧 "이 확정이 이전 확정 대비 무엇을 추가/제거/
교체했고 CAPEX가 얼마나 변했나"이다. 이를 보려면 **두 시점의 전체 설계 상태**가 필요한데, 그게
존재하는 유일한 곳이 각 확정의 git ref다. `bombom/release`도 "Full ref-to-ref BOM diff is out of
scope **for now**"라고 명시해 둔 다음 단계였다.

기존 dashboard의 "릴리즈 추이"는 placement의 release 태그를 누적 합산하는 **가법(additive)**
근사다 — 추가만 표현하고 제거/교체는 못 본다. 그래서 별도의 ref-to-ref diff가 필요하다.

## Decision
`compare_releases(ws, root, base, head, subpath)` — 두 ref의 rack YAML을 읽어 **슬롯 단위로** diff.

- **비교 단위 = (rack 파일경로, 바닥 U position)**. 같은 슬롯에 다른 device = **교체(changed)**,
  한쪽에만 있는 슬롯 = **추가/제거**. qty 변화도 changed로 본다. (대안: device 슬러그 집합 비교 →
  같은 모델을 옮기거나 슬롯을 바꾼 경우를 구분 못 함 → 기각.)
- **ref 소스**: 확정 태그명(= confirmation id)을 git ref로 직접 사용한다. 추가로 특수 ref
  `WORKING`(작업본=현재 워킹트리)을 지원해 "다음 확정이 직전 릴리즈 대비 무엇을 바꾸나"를 본다.
  태그 ref는 `git show <ref>:<rack>`로, WORKING은 `load_racks`로 읽고 **동일한 (repo-상대경로,
  position) 키 모양**으로 정규화한다(WORKING은 `.resolve().relative_to(root)`).
- **가격 = 현재 가격표(양쪽 동일, as_of=today)**. CAPEX 델타가 **설계 변화만** 격리하도록 의도한
  선택 — 시점별 절대 평가는 report/dashboard가 담당한다. (대안: 각 ref 시점의 pricing 읽기 →
  설계 변화와 가격 변동이 뒤섞임 → 기각, 필요하면 후속.)
- **안전성**: base/head는 `WORKING` 또는 `_SAFE_ID`(+`..` 금지)만 허용 → git 옵션/인자
  주입·traversal 차단(리스트형 subprocess라 shell 주입은 구조적으로 불가). subpath는 `_resolve`로
  워크스페이스 내부로 제한, `--` 뒤 위치 인자로 전달. 읽기는 `/racks/*.yaml` blob으로만 한정 →
  임의 파일 읽기 불가(보안 리뷰 PASS).

## Consequences
- 신규: `bombom/release/diff.py`, `GET /api/release/diff?base&head&path`, `/diff` 페이지
  (`web/diff.html`: 추가/제거/교체 표 + CAPEX 델타), viewer/editor 네비에 `변경비교` 링크.
- 가법 근사(dashboard 추이)와 달리 **제거/교체를 정확히** 보여준다 — decommission 워크플로의
  가시성 축을 완성. 실제 제거/교체 행위 자체는 에디터의 working-tree 편집으로 이미 가능했다.
- 알려진 한계(보안 Low, 비차단): 큰 서브트리는 rack당 `git show` 1프로세스 → 팬아웃. 내부
  읽기전용 도구라 수용. 필요시 `git cat-file --batch`로 일괄화.
- 테스트: 추가+제거+교체 한 diff, WORKING 비교(빈 결과로 키 정합 검증), 동일 ref 빈 결과, unsafe
  ref 400, 페이지 served. 109 pass, ruff clean.

## Override conditions
시점별 평가(각 ref의 pricing 반영)나 태그 간 BOM 전체(custom line item 포함) diff가 필요해지면
`compare_releases`에 valuation 시점을 ref별로 분리하고 custom_line_items까지 단위에 포함한다.
팬아웃이 문제되면 `git cat-file --batch` 일괄 읽기로 교체한다.
