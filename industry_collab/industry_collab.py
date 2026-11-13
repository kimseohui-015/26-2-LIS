"""
지표 2. 산학/외부 협업 비율  (담당: 김유하)

학생 질문: "이 랩은 기업 과제 중심인가, 학술 연구 중심인가? 밖과 얼마나 협업하나?"

[계산식]  (팀 목업 JSON의 collaboration 값 사용)
- 기업 공저 비율    = industry_papers / total_papers
- 외부 협업 비율    = external_papers / total_papers
- 논문 구성 3분할   = 기업 협업(industry) / 기타 외부 기관(external - industry) / 내부 연구(total - external)
  (기업 공저 논문은 외부 협업 논문에 포함된다고 봄)

[한계] 공동 '과제' 수가 아니라 공동 '논문' 기준. OpenAlex 소속 정보가 빠진 논문은 협업 없음으로 세어져
       실제보다 낮게 나올 수 있음.

[사용법]
- 혼자 테스트:   streamlit run industry_collab.py
- 조장 조립용:   from industry_collab import render_industry_collab
                 render_industry_collab(data["lab_A"], data["lab_B"])
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

# 팀 목업 JSON 파일 경로: 26-2-LIS 맨 위에 있는 조원 파일을 그대로 읽음.
# (이 파이썬 파일은 26-2-LIS/industry_collab/ 폴더 안에 있다고 가정)
MOCK_PATH = Path(__file__).parent.parent / "mock-up data.json"


# ---------- 1. 계산 ----------

def _pct(n, d):
    return round(n / d * 100, 1) if d else 0.0


def compute_industry_collab(lab):
    """연구실 1곳의 산학/외부 협업 지표 계산"""
    total = lab.get("total_papers", 0) or 0
    collab = lab.get("collaboration", {}) or {}
    external = collab.get("external_papers", 0) or 0
    industry = collab.get("industry_papers", 0) or 0

    return {
        "lab_name": lab.get("lab_name", ""),
        "professor": lab.get("professor", ""),
        "total": total,
        "industry": industry,
        "external": external,
        "industry_ratio": _pct(industry, total),
        "external_ratio": _pct(external, total),
        "split": {
            "기업 협업": _pct(industry, total),
            "기타 외부 기관": _pct(max(external - industry, 0), total),
            "내부 연구": _pct(max(total - external, 0), total),
        },
        # 목업에 아직 없는 값: 나중에 데이터가 생기면 자동으로 화면에 나옴
        "partners": collab.get("industry_partners", []),
    }


# ---------- 2. 화면 ----------

def _pills(names):
    """파트너 기업 이름을 알약 모양 태그로"""
    if not names:
        return ("<span style='display:inline-block;padding:3px 10px;border-radius:999px;"
                "background:#f3f4f6;color:#6b7280;font-size:13px'>정보 없음 · 수집 예정</span>")
    style = ("display:inline-block;padding:3px 10px;margin:2px;border-radius:999px;"
             "background:#eef2ff;color:#3730a3;font-size:13px")
    return "".join(f"<span style='{style}'>{n}</span>" for n in names)


def _lab_column(r):
    st.markdown(f"#### {r['lab_name']}")
    st.caption(f"{r['professor']} 교수 · 논문 {r['total']}편 기준")
    st.write(f"기업 공저 **{r['industry_ratio']}%** ({r['industry']}편)")
    st.progress(min(r["industry_ratio"] / 100, 1.0))
    st.write(f"외부 기관 협업 **{r['external_ratio']}%** ({r['external']}편)")
    st.progress(min(r["external_ratio"] / 100, 1.0))
    st.markdown("**주요 파트너 기업**")
    st.markdown(_pills(r["partners"]), unsafe_allow_html=True)


def _preference_sentence(ra, rb, level):
    """이용자 선호(중요도)에 따라 한 줄 해석"""
    if level == "상관없음":
        return "산학 협업은 크게 상관없다고 하셨으니, 다른 지표를 중심으로 비교해 보세요."
    key = "industry_ratio" if level == "매우 중요" else "external_ratio"
    label = "기업 공저" if level == "매우 중요" else "외부 기관 협업"
    if abs(ra[key] - rb[key]) < 5:
        return f"{label} 기준으로는 두 연구실이 비슷해요 ({ra[key]}% vs {rb[key]}%)."
    closer = ra if ra[key] > rb[key] else rb
    return f"내 기준에는 **{closer['lab_name']}**이 더 가까워 보여요 ({label} {closer[key]}%)."


def render_industry_collab(lab_a, lab_b):
    """조장이 import해서 부르는 함수: 두 연구실 데이터를 받아 지표 2 화면을 그림"""
    ra, rb = compute_industry_collab(lab_a), compute_industry_collab(lab_b)

    st.subheader("🤝 기업 과제 중심인가, 학술 연구 중심인가?")
    with st.expander("ⓘ 계산 방법과 한계"):
        st.markdown(
            "- **기업 공저 비율** = 기업 소속 공저자가 있는 논문 수 ÷ 전체 논문 수\n"
            "- **외부 기관 협업** = 소속 학교 외 기관 공저자가 있는 논문 수 ÷ 전체 논문 수\n"
            "- 출처: OpenAlex 공저자 소속 정보\n"
            "- 한계: 공동 '과제'가 아니라 공동 '논문' 기준이에요. 소속 정보가 빠진 논문은 "
            "협업 없음으로 세어져 실제보다 낮을 수 있어요."
        )

    # (1) 좌우 비교 카드: 게이지 바 + 파트너 태그
    col_a, col_b = st.columns(2)
    with col_a:
        _lab_column(ra)
    with col_b:
        _lab_column(rb)

    # (2) 논문 구성 3분할 막대 (산학 vs 학술 한눈에)
    st.markdown("**논문 구성 비교 (%)**")
    split = pd.DataFrame([ra["split"], rb["split"]], index=[ra["lab_name"], rb["lab_name"]])
    st.bar_chart(split, horizontal=True, color=["#4f46e5", "#a5b4fc", "#e5e7eb"])

    # (3) 이용자 선호 선택 → 해석 문장
    level = st.radio("나에게 기업·외부 협업은 얼마나 중요한가요?",
                     ["매우 중요", "보통", "상관없음"], horizontal=True, key="industry_pref")
    st.info(_preference_sentence(ra, rb, level))

    # 3줄 Brief용 한 줄 요약 (조장이 가져다 쓸 수 있게 반환)
    if abs(ra["external_ratio"] - rb["external_ratio"]) < 5:
        summary = f"두 연구실의 외부 협업 비율은 {ra['external_ratio']}% vs {rb['external_ratio']}%로 비슷해요."
    else:
        more, less = (ra, rb) if ra["external_ratio"] > rb["external_ratio"] else (rb, ra)
        times = more["external_ratio"] / less["external_ratio"] if less["external_ratio"] else 0
        summary = (f"{more['lab_name']}은 학교 밖 협업이 {more['external_ratio']}%로 "
                   + (f"{times:.1f}배 많아 " if times else "")
                   + "외부 기관과 일할 기회가 많을 수 있어요.")
    return {"lab_a": ra, "lab_b": rb, "summary": summary}


# ---------- 3. 혼자 테스트용 ----------

if __name__ == "__main__":
    st.set_page_config(page_title="산학/외부 협업 비율", layout="wide")
    data = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    result = render_industry_collab(data["lab_A"], data["lab_B"])
    st.caption("3줄 Brief용 요약: " + result["summary"])
