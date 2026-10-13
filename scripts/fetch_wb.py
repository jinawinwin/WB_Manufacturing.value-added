#!/usr/bin/env python3
"""World Bank API 크롤러: 제조업 부가가치(% of GDP, US$)를 수집해 data/ 에 저장하고 docs/data.json 을 생성한다.
사용: python scripts/fetch_wb.py [--offline data/raw_sample.json]
"""
import argparse, json, sys, time, urllib.request, datetime as dt
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.worldbank.org/v2"
IND = {"share": "NV.IND.MANF.ZS", "usd": "NV.IND.MANF.CD"}
CAGR_YEARS = [5, 10, 15, 20, 25, 30]

def get(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2 ** i)

def paged(path):
    out, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        d = get(f"{API}{path}{sep}format=json&per_page=20000&page={page}")
        meta, rows = d[0], d[1] or []
        out += rows
        if page >= meta["pages"]: return out
        page += 1

def crawl():
    countries = paged("/country")
    ctry = [{"iso3": c["id"], "name": c["name"], "region": c["region"]["value"],
             "income": c["incomeLevel"]["value"]} for c in countries if c["region"]["id"] != "NA"]
    series = {}
    for key, code in IND.items():
        rows = paged(f"/country/all/indicator/{code}?date=1960:{dt.date.today().year}")
        series[key] = [{"iso3": r["countryiso3code"], "year": int(r["date"]), "value": r["value"]}
                       for r in rows if r["value"] is not None and r["countryiso3code"]]
    return {"countries": ctry, "series": series, "fetched": dt.datetime.utcnow().isoformat() + "Z"}

CONT_KO = {"AF": "아프리카", "AS": "아시아", "EU": "유럽", "NA": "북미", "SA": "남미", "OC": "오세아니아"}
def continent(iso3):
    import pycountry_convert as pc
    try:
        return CONT_KO[pc.country_alpha2_to_continent_code(pc.country_alpha3_to_country_alpha2(iso3))]
    except Exception:
        return {"XKX": "유럽", "TLS": "아시아"}.get(iso3, "기타")

def build(raw):
    cm = pd.DataFrame(raw["countries"]).set_index("iso3")
    cm["continent"] = [continent(i) for i in cm.index]
    wide = {}
    for k, rows in raw["series"].items():
        df = pd.DataFrame(rows)
        df = df[df.iso3.isin(cm.index)]
        wide[k] = df.pivot_table(index="iso3", columns="year", values="value")
    share, usd = wide["share"], wide["usd"]
    # 기준연도: 데이터가 100개국 이상인 가장 최근 연도 (2025가 아직 미공시면 자동 후퇴)
    cov = share.notna().sum()
    base = int(max(y for y in cov.index if cov[y] >= 100 and y <= dt.date.today().year - 1))

    def cagr(df, n):
        y0 = base - n
        if y0 not in df.columns: return pd.Series(dtype=float)
        a, b = df[y0], df[base]
        ok = (a > 0) & (b > 0)
        return ((b[ok] / a[ok]) ** (1 / n) - 1) * 100

    cg = {k: {n: cagr(df, n) for n in CAGR_YEARS} for k, df in wide.items()}
    countries = []
    for iso, m in cm.iterrows():
        def v(df, y):
            x = df.loc[iso, y] if iso in df.index and y in df.columns else None
            return None if x is None or pd.isna(x) else round(float(x), 3)
        countries.append({
            "iso3": iso, "name": m["name"], "continent": m["continent"], "region": m["region"],
            "share": v(share, base), "usd": v(usd, base),
            "cagr_usd": {str(n): (round(float(cg["usd"][n][iso]), 2) if iso in cg["usd"][n].index else None) for n in CAGR_YEARS},
            "cagr_share": {str(n): (round(float(cg["share"][n][iso]), 2) if iso in cg["share"][n].index else None) for n in CAGR_YEARS},
            "ts": {str(y): v(share, y) for y in share.columns if y >= 1990 and v(share, y) is not None},
            "ts_usd": {str(y): v(usd, y) for y in usd.columns if y >= 1990 and v(usd, y) is not None},
        })
    return {"base_year": base, "fetched": raw["fetched"], "countries": countries,
            "indicators": {"share": "Manufacturing, value added (% of GDP) NV.IND.MANF.ZS",
                           "usd": "Manufacturing, value added (current US$) NV.IND.MANF.CD"}}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--offline")
    a = ap.parse_args()
    raw = json.load(open(a.offline)) if a.offline else crawl()
    if not a.offline: (ROOT / "data/raw.json").write_text(json.dumps(raw))
    out = build(raw)
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/data.json").write_text(json.dumps(out, ensure_ascii=False))
    rows = [{k: c[k] for k in ("iso3", "name", "continent", "region", "share", "usd")} |
            {f"cagr_usd_{n}y": c["cagr_usd"][str(n)] for n in CAGR_YEARS} for c in out["countries"]]
    pd.DataFrame(rows).to_csv(ROOT / "docs/manufacturing_latest.csv", index=False, encoding="utf-8-sig")
    long = [{"iso3": c["iso3"], "name": c["name"], "year": int(y), "share_pct_gdp": s, "usd": c["ts_usd"].get(y)}
            for c in out["countries"] for y, s in c["ts"].items()]
    pd.DataFrame(long).to_csv(ROOT / "docs/manufacturing_timeseries.csv", index=False, encoding="utf-8-sig")
    print(f"base year {out['base_year']}, {len(out['countries'])} countries")
