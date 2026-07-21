import os
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# 설정: 데이터 파일 (이 코드 파일과 같은 폴더에 있어야 함)
# =========================================================
DATA_FILE = "202606_202606_data3.csv"

# =========================================================
# 페이지 설정
# =========================================================
st.set_page_config(
    page_title="연령대(5세 급간)별 인구 최다·최소 지역",
    page_icon="🔟",
    layout="wide",
)

st.title("🔟 연령대(5세 급간)별 인구 최다 · 최소 지역 Top 10")
st.caption("원하는 5세 급간(예: 20~24세)을 선택하면, 그 연령대 인구가 가장 많은 지역 Top 10과 가장 적은 지역 Top 10을 각각 보여줍니다.")


# =========================================================
# 데이터 로드
# =========================================================
@st.cache_data
def load_data(file):
    """CSV를 읽어 계/남/여 연령별 인구수를 정리하고, 지역명/행정단위를 파싱한다."""
    df = pd.read_csv(file, encoding="cp949", low_memory=False)

    region_col = df.columns[0]

    # 콤마 제거 후 숫자형 변환
    for col in df.columns[1:]:
        df[col] = df[col].astype(str).str.replace(",", "", regex=False)
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

    return df, age_cols


if not os.path.exists(DATA_FILE):
    st.error(
        f"데이터 파일을 찾을 수 없습니다: `{DATA_FILE}`\n\n"
        "이 코드 파일과 같은 폴더(레포지토리 루트)에 해당 CSV 파일을 함께 올려주세요."
    )
    st.stop()

df, age_cols = load_data(DATA_FILE)

if not age_cols:
    st.error("연령별 인구 데이터 컬럼을 찾지 못했습니다. CSV 형식을 확인해주세요.")
    st.stop()


# =========================================================
# 5세 급간 정의: 0~4세, 5~9세, ... 95~99세, 100세 이상
# =========================================================
AGE_BAND_SIZE = 5
band_definitions = []
for start in range(0, 100, AGE_BAND_SIZE):
    end = start + AGE_BAND_SIZE - 1
    band_definitions.append((f"{start}~{end}세", list(range(start, end + 1))))
band_definitions.append(("100세 이상", [100]))
band_lookup = dict(band_definitions)


# =========================================================
# 옵션 선택
# =========================================================
col1, col2, col3 = st.columns([1.3, 1, 1.3])

with col1:
    band_labels = [b[0] for b in band_definitions]
    default_idx = band_labels.index("20~24세") if "20~24세" in band_labels else 0
    selected_band = st.selectbox("연령대(5세 급간) 선택", options=band_labels, index=default_idx)

with col2:
    band_metric = st.radio("기준", options=["인구수", "비율(%)"], horizontal=True)

with col3:
    band_level = st.radio("행정 단위", options=["읍면동", "시군구", "시도"], horizontal=True)

band_ages = band_lookup[selected_band]
band_cols = [c[0] for c in age_cols if c[1] == "계" and c[2] in band_ages]


# =========================================================
# 집계 및 정렬
# =========================================================
if not band_cols:
    st.warning("선택한 연령대에 해당하는 컬럼을 찾지 못했습니다.")
else:
    total_pop_col = next((c for c in df.columns if c.endswith("_계_총인구수")), None)

    level_df = df[df["단위"] == band_level].copy()
    level_df = level_df[level_df[total_pop_col] > 0]

    level_df["연령대인구수"] = level_df[band_cols].sum(axis=1)
    level_df["연령대비율(%)"] = (level_df["연령대인구수"] / level_df[total_pop_col] * 100).round(2)

    sort_col = "연령대인구수" if band_metric == "인구수" else "연령대비율(%)"

    top10 = level_df.sort_values(sort_col, ascending=False).head(10)
    bottom10 = level_df.sort_values(sort_col, ascending=True).head(10)

    # =========================================================
    # 그래프 + 테이블 (Top10 / Bottom10)
    # =========================================================
    tcol, bcol = st.columns(2)

    with tcol:
        st.markdown(f"**🔼 {selected_band} 인구 최다 지역 Top 10 ({band_level})**")
        fig_top = go.Figure(
            go.Bar(
                x=top10[sort_col][::-1],
                y=top10["지역명"][::-1],
                orientation="h",
                marker=dict(color="#2ca02c"),
                hovertemplate="%{y}<br>" + sort_col + ": %{x:,.2f}<extra></extra>",
            )
        )
        fig_top.update_layout(
            xaxis_title=sort_col,
            yaxis_title="",
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_top, use_container_width=True)

        top10_display = top10[["지역명", total_pop_col, "연령대인구수", "연령대비율(%)"]].rename(
            columns={total_pop_col: "총인구수"}
        )
        top10_display.insert(0, "순위", range(1, len(top10_display) + 1))
        top10_display["총인구수"] = top10_display["총인구수"].astype(int)
        top10_display["연령대인구수"] = top10_display["연령대인구수"].astype(int)
        st.dataframe(top10_display, use_container_width=True, hide_index=True)

    with bcol:
        st.markdown(f"**🔽 {selected_band} 인구 최소 지역 Top 10 ({band_level})**")
        fig_bottom = go.Figure(
            go.Bar(
                x=bottom10[sort_col][::-1],
                y=bottom10["지역명"][::-1],
                orientation="h",
                marker=dict(color="#d62728"),
                hovertemplate="%{y}<br>" + sort_col + ": %{x:,.2f}<extra></extra>",
            )
        )
        fig_bottom.update_layout(
            xaxis_title=sort_col,
            yaxis_title="",
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_bottom, use_container_width=True)

        bottom10_display = bottom10[["지역명", total_pop_col, "연령대인구수", "연령대비율(%)"]].rename(
            columns={total_pop_col: "총인구수"}
        )
        bottom10_display.insert(0, "순위", range(1, len(bottom10_display) + 1))
        bottom10_display["총인구수"] = bottom10_display["총인구수"].astype(int)
        bottom10_display["연령대인구수"] = bottom10_display["연령대인구수"].astype(int)
        st.dataframe(bottom10_display, use_container_width=True, hide_index=True)

st.caption("데이터 출처: 행정안전부 주민등록 연령별 인구현황(월간)")
