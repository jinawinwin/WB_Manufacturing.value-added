# WB Manufacturing value-added 대시보드
World Bank API(NV.IND.MANF.ZS, NV.IND.MANF.CD)를 수집해 `docs/`에 정적 대시보드로 게시합니다.

## 시작하기
1. 저장소 Settings → Pages → Source: `main` / `/docs`
2. Actions → *Update World Bank manufacturing data* → **Run workflow** (최초 1회)
3. 이후 매년 1월·7월 10일(UTC 00:00) 자동 실행

## 로컬 실행
`pip install pandas openpyxl pycountry-convert && python scripts/fetch_wb.py`

기준연도는 국가 100개 이상 데이터가 있는 가장 최근 연도로 자동 결정됩니다. 대륙은 pycountry-convert 기준(WB 지역과 다름).
