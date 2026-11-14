"""지표 5. 연구 산출 연속성
질문 대상: 논문이 끊김 없이 꾸준히 나오는가? 최근에 줄고 있지는 않은가?

수식 (기간 2021~2025, 완결된 5년)
- 연도별 논문 수  n_y  (y = 2021..2025)
- 공백 연도 수     gap = n_y 가 0인 해의 개수
- 이전 평균        early = (n_2021 + n_2022 + n_2023) / 3
- 최근 평균        recent = (n_2024 + n_2025) / 2
- 최근 추세        trend = recent / early   (early가 0이면 판정 생략)
- 활동 개월 비율   active_months = 논문이 1편 이상 나온 달 수 / 60개월

신호등
- 초록 : gap == 0 이고 trend >= 0.7
- 노랑 : gap == 1 이거나 trend < 0.7
- 빨강 : gap >= 2
"""
import pandas as pd
import streamlit as st

START, END = 2021, 2025
YEARS = list(range(START, END + 1))
TREND_CUT = 0.7

SIGNAL = {
    "green": ("🟢", "꾸준함", "5년 내내 논문이 나왔고 최근에도 페이스가 유지됨."),
    "yellow": ("🟡", "주의", "공백 연도가 1년 있거나 최근 논문 수가 줄어든 상태임."),
    "red": ("🔴", "공백 많음", "논문이 나오지 않은 해가 2년 이상임."),
}


def compute_continuity(lab: dict) -> dict:
    works = [w for w in lab["works"] if START <= w["year"] <= END]

    by_year = {y: 0 for y in YEARS}
    by_month = {(y, m): 0 for y in YEARS for m in range(1, 13)}
    for w in works:
        by_year[w["year"]] += 1
        month = int(w["publication_date"][5:7]) if w.get("publication_date") else 1
        by_month[(w["year"], month)] += 1

    gap_years = [y for y in YEARS if by_year[y] == 0]
    early = sum(by_year[y] for y in YEARS[:3]) / 3
    recent = sum(by_year[y] for y in YEARS[3:]) / 2
    trend = round(recent / early, 2) if early > 0 else None

    if len(gap_years) >= 2:
        signal = "red"
    elif len(gap_years) == 1 or (trend is not None and trend < TREND_CUT):
        signal = "yellow"
    else:
        signal = "green"

    active = sum(1 for v in by_month.values() if v > 0)
    return {
        "total": len(works),
        "by_year": by_year,
        "by_month": by_month,
        "gap_years": gap_years,
        "early_avg": round(early, 1),
        "recent_avg": round(recent, 1),
        "trend": trend,
        "active_month_ratio": round(active / len(by_month) * 100, 1),
        "signal": signal,
    }


def _grass_html(by_month: dict) -> str:
    """GitHub 잔디 달력 모양: 가로 = 월, 세로 = 연도."""
    peak = max(by_month.values()) or 1
    shades = ["#EBEDF0", "#9BE9A8", "#40C463", "#30A14E", "#216E39"]
    cell = "display:inline-block;width:18px;height:18px;margin:2px;border-radius:3px;"
    rows = []
    for y in YEARS:
        cells = []
        for m in range(1, 13):
            n = by_month[(y, m)]
            level = 0 if n == 0 else min(4, 1 + int((n - 1) / peak * 4))
            cells.append(f'<span title="{y}년 {m}월 · {n}편" style="{cell}background:{shades[level]}"></span>')
        rows.append(f'<div style="display:flex;align-items:center"><span style="width:44px;font-size:12px">{y}</span>{"".join(cells)}</div>')
    return "".join(rows)


def render_continuity(labs: list[dict]) -> None:
    st.subheader("5. 연구 산출 연속성")
    st.caption("논문이 끊김 없이 꾸준히 나오는가? 최근에 줄고 있지는 않은가?")

    results = [(lab, compute_continuity(lab)) for lab in labs]

    cols = st.columns(len(labs))
    for col, (lab, r) in zip(cols, results):
        icon, label, desc = SIGNAL[r["signal"]]
        with col:
            st.markdown(f"**{lab['lab_name']}**")
            st.markdown(f"### {icon} {label}")
            st.caption(desc)
            gaps = ", ".join(map(str, r["gap_years"])) if r["gap_years"] else "없음"
            trend = f"{r['trend']}배" if r["trend"] is not None else "판정 불가"
            st.write(f"공백 연도: **{gaps}** · 최근 추세(2024–25 ÷ 2021–23): **{trend}**")
            st.write(f"논문이 나온 달: 60개월 중 **{r['active_month_ratio']}%**")
            st.markdown(_grass_html(r["by_month"]), unsafe_allow_html=True)

    st.markdown("**연도별 논문 수**")
    df = pd.DataFrame({lab["lab_name"]: r["by_year"] for lab, r in results})
    df.index = df.index.astype(str)
    st.line_chart(df)


if __name__ == "__main__":
    import json
    data = json.load(open("mock_labs.json", encoding="utf-8"))
    render_continuity(data["labs"])
