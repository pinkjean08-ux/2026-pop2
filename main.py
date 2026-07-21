import os
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# 설정: 데이터 파일 (main.py와 같은 폴더에 있어야 함)
# =========================================================
DATA_FILE = "202606_202606_data3_.csv"

# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="연령별 인구현황 대시보드",
    page_icon="📊",
    layout="wide",
)

st.title("📊 지역별 연령별 인구 구조 대시보드")
st.caption("행정안전부 연령별 인구현황(월간) 데이터를 기반으로 선택한 지역의 연령별 인구 구조를 꺾은선 그래프로 보여줍니다.")


# =========================================================
# 데이터 로드
# =========================================================
@st.cache_data
def load_data(file):
    """CSV를 읽어 계/남/여 연령별 인구수를 long-format으로 정리한다."""
    df = pd.read_csv(file, encoding="cp949", low_memory=False)

    region_col = df.columns[0]

    # 콤마 제거 후 숫자형 변환
    for col in df.columns[1:]:
        df[col] = (
            df[col].astype(str).str.replace(",", "", regex=False)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 행정구역명 / 행정코드 분리
    # 예: "서울특별시 종로구 청운효자동(1111051500)" -> 이름 / 코드
    def split_region(x):
        m = re.match(r"^(.*?)\s*\((\d+)\)\s*$", str(x).strip())
        if m:
            return m.group(1).strip(), m.group(2)
        return str(x).strip(), None

    names, codes = zip(*df[region_col].map(split_region))
    df["지역명"] = names
    df["행정코드"] = codes

    # 연령 컬럼 파싱: "2026년06월_계_0세", "2026년06월_계_100세 이상" 등
    age_pattern = re.compile(r"^(?P<ym>\d{4}년\d{2}월)_(?P<gender>계|남|여)_(?P<age>\d+세|\d+세 이상)$")

    age_cols = []  # (원본 컬럼명, 성별, 연령숫자, 연령라벨)
    for col in df.columns:
        m = age_pattern.match(col)
        if m:
            age_label = m.group("age")
            age_num_match = re.match(r"(\d+)", age_label)
            age_num = int(age_num_match.group(1)) if age_num_match else 999
            age_cols.append((col, m.group("gender"), age_num, age_label))

    return df, age_cols, region_col


if not os.path.exists(DATA_FILE):
    st.error(
        f"데이터 파일을 찾을 수 없습니다: `{DATA_FILE}`\n\n"
        "app.py와 같은 폴더(레포지토리 루트)에 해당 CSV 파일을 함께 올려주세요."
    )
    st.stop()

df, age_cols, region_col = load_data(DATA_FILE)

if not age_cols:
    st.error("연령별 인구 데이터 컬럼을 찾지 못했습니다. CSV 형식을 확인해주세요.")
    st.stop()

all_region_names = sorted(df["지역명"].unique().tolist())


# =========================================================
# 사이드바: 지역 선택 (검색 입력 + 선택 콤보)
# =========================================================
st.sidebar.header("🔎 지역 선택")

search_text = st.sidebar.text_input("지역명 검색 (예: 종로, 해운대, 강남)", "")

if search_text.strip():
    filtered_regions = [r for r in all_region_names if search_text.strip() in r]
else:
    filtered_regions = all_region_names

if not filtered_regions:
    st.sidebar.error("검색 결과가 없습니다. 다른 검색어를 입력해주세요.")
    st.stop()

default_region = filtered_regions[0]
main_region = st.sidebar.selectbox(
    "기준 지역 선택",
    options=filtered_regions,
    index=0,
)

compare_regions = st.sidebar.multiselect(
    "비교할 지역 추가 (선택)",
    options=[r for r in all_region_names if r != main_region],
)

gender_options = st.sidebar.multiselect(
    "표시할 성별",
    options=["계", "남", "여"],
    default=["계"],
)

if not gender_options:
    st.sidebar.warning("최소 1개 이상의 성별을 선택해주세요.")
    st.stop()

selected_regions = [main_region] + compare_regions


# =========================================================
# 데이터 가공: 선택 지역 x 성별 별 연령 인구수 시리즈 생성
# =========================================================
def build_series(region_name, gender):
    row = df[df["지역명"] == region_name]
    if row.empty:
        return None, None
    row = row.iloc[0]

    cols = [c for c in age_cols if c[1] == gender]
    cols = sorted(cols, key=lambda c: c[2])  # 연령 순 정렬

    ages = [c[3] for c in cols]
    values = [row[c[0]] for c in cols]
    return ages, values


# =========================================================
# 그래프: Plotly 꺾은선 그래프
# =========================================================
st.subheader(f"연령별 인구 구조: {', '.join(selected_regions)}")

fig = go.Figure()

color_palette = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
]
line_dash_by_gender = {"계": "solid", "남": "dot", "여": "dash"}

color_idx = 0
for region_name in selected_regions:
    region_color = color_palette[color_idx % len(color_palette)]
    color_idx += 1
    for gender in gender_options:
        ages, values = build_series(region_name, gender)
        if ages is None:
            continue
        fig.add_trace(
            go.Scatter(
                x=ages,
                y=values,
                mode="lines",
                name=f"{region_name} - {gender}",
                line=dict(color=region_color, dash=line_dash_by_gender.get(gender, "solid")),
                hovertemplate="연령: %{x}<br>인구수: %{y:,}명<extra>%{fullData.name}</extra>",
            )
        )

fig.update_layout(
    xaxis_title="연령",
    yaxis_title="인구수 (명)",
    hovermode="x unified",
    legend_title="지역 - 성별",
    height=600,
    margin=dict(l=40, r=40, t=40, b=40),
)
fig.update_xaxes(tickangle=-45, tickmode="linear", dtick=5)

st.plotly_chart(fig, use_container_width=True)


# =========================================================
# 요약 통계 테이블
# =========================================================
st.subheader("📋 지역 요약")

summary_rows = []
for region_name in selected_regions:
    row = df[df["지역명"] == region_name]
    if row.empty:
        continue
    row = row.iloc[0]

    total_col = next((c[0] for c in age_cols if c[1] == "계"), None)
    summary = {"지역명": region_name}

    for gender in ["계", "남", "여"]:
        total_pop_cols = [c for c in df.columns if c.endswith(f"_{gender}_총인구수")]
        if total_pop_cols:
            summary[f"{gender} 총인구수"] = int(row[total_pop_cols[0]])

    summary_rows.append(summary)

summary_df = pd.DataFrame(summary_rows)
st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.caption("데이터 출처: 행정안전부 주민등록 연령별 인구현황(월간)")
