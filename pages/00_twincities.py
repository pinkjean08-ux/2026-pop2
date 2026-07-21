import os
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# 설정: 데이터 파일 (app.py와 같은 폴더에 있어야 함)
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

    # 행정구역 단위 구분 (시도 / 시군구 / 읍면동)
    # 코드 예: 1100000000(시도) / 1111000000(시군구) / 1111051500(읍면동)
    def get_level(code):
        if code is None:
            return "기타"
        if code[2:] == "00000000":
            return "시도"
        if code[5:] == "00000":
            return "시군구"
        return "읍면동"

    df["단위"] = df["행정코드"].map(get_level)

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


# =========================================================
# 전국 유사 지역 Top 5 (인구 구조 유사도)
# =========================================================
st.subheader("🧭 전국에서 인구 구조가 가장 비슷한 지역 Top 5")
st.caption("연령대별 인구 '비중'(전체 인구 대비 %)의 모양을 비교하여, 총인구 규모와 상관없이 구조가 비슷한 지역을 찾습니다. 비교는 선택한 지역과 같은 행정 단위(시도/시군구/읍면동)끼리만 수행합니다.")

# 계(전체) 성별 연령 컬럼 (연령 순 정렬)
total_age_cols = sorted([c for c in age_cols if c[1] == "계"], key=lambda c: c[2])
total_col_names = [c[0] for c in total_age_cols]
total_age_labels = [c[3] for c in total_age_cols]

main_row = df[df["지역명"] == main_region]

if main_row.empty:
    st.warning("선택한 지역의 데이터를 찾을 수 없습니다.")
else:
    main_level = main_row.iloc[0]["단위"]

    # 같은 행정 단위(시도/시군구/읍면동)의 후보 지역만 비교 대상으로 사용
    pool = df[(df["단위"] == main_level) & (df["지역명"] != main_region)].copy()

    # 총인구수가 0이면 비중 계산이 불가능하므로 제외
    total_pop_col = next((c for c in df.columns if c.endswith("_계_총인구수")), None)
    pool = pool[pool[total_pop_col] > 0]
    main_total_pop = main_row.iloc[0][total_pop_col]

    if pool.empty or main_total_pop in (0, None) or pd.isna(main_total_pop):
        st.warning("비교할 지역 데이터가 충분하지 않습니다.")
    else:
        # 연령별 인구 비중(%) 행렬 구성
        main_share = main_row.iloc[0][total_col_names].astype(float).values / main_total_pop
        pool_share = pool[total_col_names].astype(float).values / pool[total_pop_col].values.reshape(-1, 1)

        # 유클리드 거리 기반 유사도 계산 (거리가 작을수록 구조가 비슷함)
        dist = np.sqrt(((pool_share - main_share) ** 2).sum(axis=1))
        pool["유사도_거리"] = dist
        pool["유사도(%)"] = (1 / (1 + dist)) * 100  # 참고용 상대 유사도 지표

        top5 = pool.sort_values("유사도_거리", ascending=True).head(5)

        # ---- Plotly 그래프: 선택 지역 vs Top5 유사 지역 (연령별 인구 비중 %) ----
        fig_sim = go.Figure()

        fig_sim.add_trace(
            go.Scatter(
                x=total_age_labels,
                y=main_share * 100,
                mode="lines",
                name=f"⭐ {main_region} (기준)",
                line=dict(color="#d62728", width=4),
                hovertemplate="연령: %{x}<br>비중: %{y:.2f}%<extra>%{fullData.name}</extra>",
            )
        )

        sim_colors = ["#1f77b4", "#2ca02c", "#9467bd", "#8c564b", "#17becf"]
        for i, (_, r) in enumerate(top5.iterrows()):
            row_share = r[total_col_names].astype(float).values / r[total_pop_col]
            fig_sim.add_trace(
                go.Scatter(
                    x=total_age_labels,
                    y=row_share * 100,
                    mode="lines",
                    name=f"{i + 1}위 {r['지역명']}",
                    line=dict(color=sim_colors[i % len(sim_colors)], width=2, dash="dot"),
                    hovertemplate="연령: %{x}<br>비중: %{y:.2f}%<extra>%{fullData.name}</extra>",
                )
            )

        fig_sim.update_layout(
            xaxis_title="연령",
            yaxis_title="전체 인구 대비 비중 (%)",
            hovermode="x unified",
            legend_title="지역 (유사도 순위)",
            height=550,
            margin=dict(l=40, r=40, t=40, b=40),
        )
        fig_sim.update_xaxes(tickangle=-45, tickmode="linear", dtick=5)

        st.plotly_chart(fig_sim, use_container_width=True)

        # ---- Top5 요약 테이블 ----
        top5_display = top5[["지역명", total_pop_col, "유사도(%)"]].rename(
            columns={total_pop_col: "총인구수"}
        )
        top5_display.insert(0, "순위", range(1, len(top5_display) + 1))
        top5_display["총인구수"] = top5_display["총인구수"].astype(int)
        top5_display["유사도(%)"] = top5_display["유사도(%)"].round(2)

        st.dataframe(top5_display, use_container_width=True, hide_index=True)

st.caption("데이터 출처: 행정안전부 주민등록 연령별 인구현황(월간)")
