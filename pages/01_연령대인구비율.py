import os
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# =========================================================
# 설정: 데이터 파일 (app.py와 같은 폴더에 있어야 함)
# =========================================================
DATA_FILE = "202606_202606_data3.csv"



# =========================================================
# 연령대(5세 급간)별 인구 최다·최소 지역 Top 10
# =========================================================
st.subheader("🔟 연령대(5세 급간)별 인구 최다 · 최소 지역 Top 10")
st.caption("원하는 5세 급간(예: 20~24세)을 선택하면, 그 연령대 인구가 가장 많은 지역 Top 10과 가장 적은 지역 Top 10을 각각 보여줍니다.")

# 5세 급간 정의: 0~4세, 5~9세, ... 95~99세, 100세 이상
AGE_BAND_SIZE = 5
band_definitions = []
for start in range(0, 100, AGE_BAND_SIZE):
    end = start + AGE_BAND_SIZE - 1
    band_definitions.append((f"{start}~{end}세", list(range(start, end + 1))))
band_definitions.append(("100세 이상", [100]))
band_lookup = dict(band_definitions)

bcol1, bcol2, bcol3 = st.columns([1.3, 1, 1.3])

with bcol1:
    band_labels = [b[0] for b in band_definitions]
    default_idx = band_labels.index("20~24세") if "20~24세" in band_labels else 0
    selected_band = st.selectbox("연령대(5세 급간) 선택", options=band_labels, index=default_idx)

with bcol2:
    band_metric = st.radio("기준", options=["인구수", "비율(%)"], horizontal=True, key="band_metric")

with bcol3:
    band_level = st.radio("행정 단위", options=["읍면동", "시군구", "시도"], horizontal=True, key="band_level")

band_ages = band_lookup[selected_band]
band_cols = [c[0] for c in age_cols if c[1] == "계" and c[2] in band_ages]

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
