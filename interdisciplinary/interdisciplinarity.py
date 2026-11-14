"""LABMATCH 학제 간 융합도.

render_interdisciplinarity(data)는 json.load()로 읽은 dict를 받는다.
팀 공통 형식은 lab_A, lab_B의 lab_name과 interdisciplinarity_demo_papers를 사용한다.
가상 표본 배열에는 id, year, field_ids만 필요하다. 배열이 없으면 산출 불가로 표시한다.
공통 논문 건수와 키워드는 융합도 산출에 사용하지 않는다.

기존 입력 형식도 지원한다. 이 형식의 필수 최상위 키는 source, labs다.
source: kind("mock" 또는 "public"), name, taxonomy. public에는 retrieved_at 추가.
labs: id, name, papers를 가진 연구실 목록.
papers: id, title, year(정수), field_ids(중복 없는 분야명/ID 문자열 목록).
field_ids는 같은 분류 체계의 같은 계층을 사용한다. 미분류는 []로 전달한다.
논문은 연구실별로 중복 제거한다. papers는 수집된 논문 전체를 전달한다.
"""

import json
from collections import Counter
from pathlib import Path


def _string(value):
    return isinstance(value, str) and bool(value.strip())


def _records(value, label, required):
    if not isinstance(value, list):
        raise ValueError(f"{label}은 배열이어야 합니다.")
    seen = set()
    for record in value:
        if not isinstance(record, dict) or any(
            not _string(record.get(key)) for key in required
        ):
            raise ValueError(f"{label}의 {', '.join(required)} 값을 확인하세요.")
        if record["id"] in seen:
            raise ValueError(f"{label}에 중복 ID가 있습니다. ({record['id']})")
        seen.add(record["id"])


def _normalize_data(data):
    if not isinstance(data, dict) or "labs" in data or not {"lab_A", "lab_B"} <= data.keys():
        return data

    labs = []
    for lab_id in ("lab_A", "lab_B"):
        lab = data[lab_id]
        if not isinstance(lab, dict) or not _string(lab.get("lab_name")):
            raise ValueError(f"{lab_id}의 lab_name을 확인하세요.")
        papers = lab.get("interdisciplinarity_demo_papers", [])
        if not isinstance(papers, list):
            raise ValueError(f"{lab_id}의 interdisciplinarity_demo_papers는 배열이어야 합니다.")
        labs.append({
            "id": lab_id,
            "name": lab["lab_name"],
            "papers": [
                {**paper, "title": "가상 논문"} if isinstance(paper, dict) else paper
                for paper in papers
            ],
        })
    return {
        "source": {
            "kind": "mock",
            "name": "팀 공통 목업에 추가한 학제 간 융합도 표본",
            "taxonomy": "데모용 대분야 분류",
        },
        "labs": labs,
    }


def validate(data):
    """입력 계약 위반 시 ValueError를 발생시킨다."""
    _validate_normalized(_normalize_data(data))


def _validate_normalized(data):
    source = data.get("source") if isinstance(data, dict) else None
    if not isinstance(source, dict) or source.get("kind") not in ("mock", "public"):
        raise ValueError("source.kind에 mock 또는 public을 지정하세요.")
    required = ["name", "taxonomy"]
    if source["kind"] == "public":
        required.append("retrieved_at")
    if any(not _string(source.get(key)) for key in required):
        raise ValueError(f"source에 {', '.join(required)} 값을 지정하세요.")

    _records(data.get("labs"), "labs", ("id", "name"))
    for lab in data["labs"]:
        papers = lab.get("papers")
        _records(papers, f"{lab['name']}의 papers", ("id", "title"))
        for paper in papers:
            year = paper.get("year")
            fields = paper.get("field_ids")
            if type(year) is not int or not 1 <= year <= 9999:
                raise ValueError(f"{paper['id']}의 year는 1~9999 정수여야 합니다.")
            if (
                not isinstance(fields, list)
                or any(not _string(field) or field != field.strip() for field in fields)
                or len(set(fields)) != len(fields)
            ):
                raise ValueError(f"{paper['id']}의 field_ids를 확인하세요.")


def summarize(papers):
    """선택 기간의 분류율, 융합도, 분야별 비중를 반환한다."""
    classified = 0
    cross_field = 0
    weights = Counter()
    for paper in papers:
        fields = paper["field_ids"]
        if fields:
            classified += 1
            cross_field += len(fields) >= 2
            for field in fields:
                weights[field] += 1 / len(fields)

    return {
        "total": len(papers),
        "classified": classified,
        "cross_field": cross_field,
        "score": 100 * cross_field / classified if classified else None,
        "coverage": 100 * classified / len(papers) if papers else None,
        "shares": {field: 100 * weight / classified for field, weight in weights.items()},
    }


def _sankey(earlier, later, earlier_label, later_label):
    import plotly.graph_objects as go

    labels = []
    indexes = {}
    sizes, starts, ends = [], [], []

    def add_link(left, right, value):
        if value <= 1e-9:
            return
        for node in (left, right):
            if node not in indexes:
                indexes[node] = len(labels)
                labels.append(node[1])
        starts.append(indexes[left])
        ends.append(indexes[right])
        sizes.append(value)

    for field in sorted(earlier.keys() | later.keys()):
        past = (0, f"{earlier_label} · {field}")
        recent = (1, f"{later_label} · {field}")
        before, after = earlier.get(field, 0), later.get(field, 0)
        add_link(past, recent, min(before, after))
        add_link(past, (1, "감소분"), before - after)
        add_link((0, "증가분"), recent, after - before)

    figure = go.Figure(go.Sankey(
        node=dict(label=labels, pad=16, thickness=15),
        link=dict(
            source=starts, target=ends, value=sizes,
            hovertemplate="%{source.label} → %{target.label}<br>%{value:.1f}%p<extra></extra>",
        ),
    ))
    figure.update_layout(height=max(380, 30 * max(len(earlier), len(later))), margin=dict(t=15, b=15))
    return figure


def _percentage(value):
    return "산출 불가" if value is None else f"{value:.1f}%"


def render_interdisciplinarity(data):
    """전달받은 JSON 데이터로 현재 Streamlit 화면에 지표를 그린다."""
    import streamlit as st

    st.header("학제 간 융합도")
    try:
        data = _normalize_data(data)
        _validate_normalized(data)
    except ValueError as error:
        st.error(str(error))
        return

    source = data["source"]
    if source["kind"] == "mock":
        st.warning(f"가상 데이터 데모 · {source['name']}")
        st.caption("화면의 수치와 그래프는 가상 논문 표본만으로 계산한 데모 결과입니다.")
    else:
        st.info(f"공개 데이터 · {source['name']} · 수집일 {source['retrieved_at']}")
    st.caption(f"분야 분류 기준 · {source['taxonomy']}")
    st.caption("융합도 = 2개 이상 분야로 분류된 논문 수 ÷ 분야 분류가 있는 논문 수 × 100")

    years = sorted({p["year"] for lab in data["labs"] for p in lab["papers"] if p["year"] >= 5})
    if not years:
        st.info("비교 기간을 설정할 수 있는 논문 자료가 없어 융합도를 산출할 수 없습니다.")
        return

    end = st.selectbox("비교 기준연도", years, index=len(years) - 1, key="labmatch_interdisciplinarity_year")
    past_label = f"{end - 4}~{end - 2}"
    recent_label = f"{end - 1}~{end}"
    st.caption(
        f"최근 5개 연도({end - 4}~{end})를 초기 3년({past_label})과 "
        f"최근 2년({recent_label})으로 나눠 기간별 분야 비중을 비교합니다."
    )

    for lab in data["labs"]:
        papers = [p for p in lab["papers"] if end - 4 <= p["year"] <= end]
        stats = summarize(papers)
        earlier = summarize([p for p in papers if p["year"] <= end - 2])
        later = summarize([p for p in papers if p["year"] >= end - 1])

        st.subheader(lab["name"])
        score, coverage, sample = st.columns(3)
        score.metric("학제 간 융합도", _percentage(stats["score"]))
        coverage.metric("분야 분류율", _percentage(stats["coverage"]))
        sample.metric(
            "가상 표본" if source["kind"] == "mock" else "수집 논문",
            f"{stats['total']}편",
        )
        st.caption(
            f"다분야 논문 {stats['cross_field']}편 / 분류 논문 {stats['classified']}편 · "
            f"초기 분류 {earlier['classified']}/{earlier['total']}편 · "
            f"최근 분류 {later['classified']}/{later['total']}편"
        )
        if not stats["classified"]:
            st.info("선택 기간에 분야가 분류된 논문이 없어 융합도를 계산할 수 없습니다.")
        elif stats["classified"] < 10 or stats["coverage"] < 70:
            st.warning("해석 주의 · 분류 논문 10편 미만 또는 분류율 70% 미만 (데모 기준)")

        st.markdown("**연구 분야 변천**")
        if earlier["shares"] and later["shares"]:
            st.plotly_chart(
                _sankey(earlier["shares"], later["shares"], past_label, recent_label),
                key=f"labmatch_interdisciplinarity_sankey_{lab['id']}",
            )
            st.caption(
                "띠의 두께는 분야 비중(%p)입니다. 같은 분야는 두 기간에 공통으로 "
                "차지한 비중을 연결하고, 나머지는 증가분·감소분으로 표시합니다. "
                "논문이나 연구자의 분야 이동은 이 자료로 확인할 수 없습니다."
            )
        else:
            st.info("두 기간에 각각 분류 논문이 있어야 생키를 표시할 수 있습니다.")

        fields = sorted(earlier["shares"].keys() | later["shares"].keys())
        if fields:
            st.table([
                {
                    "분야": field,
                    past_label: _percentage(earlier["shares"].get(field, 0) if earlier["classified"] else None),
                    recent_label: _percentage(later["shares"].get(field, 0) if later["classified"] else None),
                }
                for field in fields
            ])

    st.caption(
        "분야 비중은 논문 1편을 해당 분야 수로 균등 분배해 계산합니다. "
        "분류율은 분석에 사용한 논문 중 분야가 붙은 비율입니다. "
        "연구실 전체 논문의 수집률과 분류 정확도는 별도 확인이 필요합니다. "
        "수집 누락, 저자·연구실 식별 오류, 분야 분류 기준에 따라 결과가 달라질 수 있으며 "
        "타전공자의 적응 가능성은 이 지표로 판단하기 어렵습니다."
    )


if __name__ == "__main__":
    import streamlit as st

    try:
        with Path(__file__).with_name("mock-up-data-interdisciplinarity-demo.json").open(encoding="utf-8") as file:
            dataset = json.load(file)
    except (OSError, ValueError) as error:
        st.error(f"Mock JSON을 읽을 수 없습니다. ({error})")
    else:
        render_interdisciplinarity(dataset)
