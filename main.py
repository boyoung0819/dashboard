
import json
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


# ==================================================
# 1. 기본 설정
# ==================================================
st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

DATA_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/contents/"
    "/main/population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/contents/"
    "/main/sigungu_kr.geojson"
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .metric-card {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 14px;
        padding: 17px;
        min-height: 118px;
        background: rgba(128,128,128,0.045);
    }
    .metric-label {
        font-size: 0.9rem;
        color: #777;
        margin-bottom: 9px;
    }
    .metric-value {
        font-size: 1.4rem;
        font-weight: 700;
        overflow-wrap: anywhere;
    }
    .metric-sub {
        font-size: 0.85rem;
        color: #777;
        margin-top: 7px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🗺️ 전국 고령화 단계구분도")
st.caption(
    "연도와 인구 지표를 선택해 전국 시군구의 인구 구조를 비교해 보세요."
)


# ==================================================
# 2. 행정구역 코드 통일
# ==================================================
def normalize_code(value):
    """행정구역 코드를 문자열로 바꾸고 개편 코드를 보정합니다."""
    if pd.isna(value):
        return None

    code = str(value).strip()

    # 숫자형 코드가 12345.0처럼 들어오는 경우 처리
    if code.endswith(".0"):
        code = code[:-2]

    # 숫자 코드의 앞자리 0을 유지
    code = code.zfill(5)

    # 시도 코드 개편
    if code.startswith("42"):
        code = "51" + code[2:]
    elif code.startswith("45"):
        code = "52" + code[2:]

    # 군위군 코드 개편
    if code == "47720":
        code = "27720"

    return code


# ==================================================
# 3. 데이터 불러오기
# ==================================================
@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population():
    df = pd.read_csv(
        DATA_URL,
        compression="zip",
        dtype={"코드": str},
    )

    df.columns = df.columns.astype(str).str.strip()

    required = {"연도", "시도", "시군구", "동", "코드"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "인구 자료에 필요한 열이 없습니다: "
            + ", ".join(sorted(missing))
        )

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df[df["연도"].between(2015, 2026)].copy()

    df["코드"] = (
        df["코드"]
        .astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(5)
    )

    # 읍·면·동 코드 앞 5자리로 시군구 코드를 만듭니다.
    df["시군구코드"] = df["코드"].str[:5].map(normalize_code)

    # 인구 총계 열만 사용합니다.
    # 남_ / 여_ 열은 합산하지 않습니다.
    total_cols = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    if not total_cols:
        raise ValueError(
            "'계_0세', '계_1세'와 같은 인구 열을 찾을 수 없습니다."
        )

    for col in total_cols:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    return df, total_cols


@st.cache_data(show_spinner="시군구 경계 지도를 불러오는 중입니다...")
def load_geojson():
    response = requests.get(GEOJSON_URL, timeout=60)
    response.raise_for_status()

    geo = response.json()

    for feature in geo.get("features", []):
        props = feature.setdefault("properties", {})

        props["코드"] = normalize_code(props.get("코드"))
        props["시군구"] = str(props.get("시군구", "이름 없음"))
        props["시도"] = str(props.get("시도", "이름 없음"))

    return geo


try:
    population, total_cols = load_population()
    geojson = load_geojson()

except Exception as e:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(e)
    st.stop()


# ==================================================
# 4. 연도 선택
# ==================================================
available_years = sorted(
    population["연도"].dropna().astype(int).unique().tolist()
)

if not available_years:
    st.error("인구 데이터에서 연도를 찾을 수 없습니다.")
    st.stop()

default_index = (
    available_years.index(2026)
    if 2026 in available_years
    else len(available_years) - 1
)

year = st.select_slider(
    "📅 기준 연도",
    options=available_years,
    value=available_years[default_index],
    format_func=lambda y: f"{y}년",
)


# ==================================================
# 5. 지표 및 지도 범위 선택
# ==================================================
col1, col2 = st.columns(2)

with col1:
    metric = st.selectbox(
        "📊 표시할 인구 지표",
        ["65세 이상 비율 (고령화율)", "0~14세 비율 (유소년 비율)"],
    )

with col2:
    provinces = sorted(
        population["시도"].dropna().astype(str).unique().tolist()
    )
    province = st.selectbox(
        "📍 지도 범위",
        ["전국"] + provinces,
    )

if metric.startswith("65세"):
    value_col = "고령화율"
    value_title = "고령화율"
    unit_title = "65세 이상 비율"
    # 모든 연도에서 동일한 색 구간 사용
    breaks = [0, 19, 23, 28, 38, 100.000001]
    colors = [
        "#fff3c4",
        "#fbd58b",
        "#f4a261",
        "#df654b",
        "#941f24",
    ]
    labels = [
        "19% 미만",
        "19~23% 미만",
        "23~28% 미만",
        "28~38% 미만",
        "38% 이상",
    ]

else:
    value_col = "유소년비율"
    value_title = "유소년 비율"
    unit_title = "0~14세 비율"
    # 유소년 비율은 고령화율과 별도의 고정 구간 사용
    breaks = [0, 5, 8, 11, 14, 100.000001]
    colors = [
        "#eff3ff",
        "#c6dbef",
        "#9ecae1",
        "#4292c6",
        "#084594",
    ]
    labels = [
        "5% 미만",
        "5~8% 미만",
        "8~11% 미만",
        "11~14% 미만",
        "14% 이상",
    ]


# ==================================================
# 6. 선택한 연도 데이터 집계
# ==================================================
year_data = population[
    population["연도"] == year
].copy()

if year_data.empty:
    st.warning(f"{year}년 자료가 없습니다.")
    st.stop()

# 시군구 코드별로 모든 읍·면·동의 인구를 합산합니다.
grouped = (
    year_data.groupby("시군구코드", as_index=False)[total_cols]
    .sum()
)

# 이름은 코드별 첫 번째 값을 사용합니다.
names = (
    year_data.groupby("시군구코드", as_index=False)
    .agg({"시도": "first", "시군구": "first"})
)

grouped = grouped.merge(names, on="시군구코드", how="left")

# 전체 인구는 '계_' 열만 합산합니다.
grouped["전체인구"] = grouped[total_cols].sum(axis=1)


def get_age(column):
    """계_0세, 계_65세, 계_100세 이상에서 나이를 읽습니다."""
    suffix = column.replace("계_", "").strip()

    if "100세 이상" in suffix:
        return 100

    match = re.search(r"(\d+)\s*세", suffix)

    if match:
        return int(match.group(1))

    return None


age_map = {col: get_age(col) for col in total_cols}

elderly_cols = [
    col for col, age in age_map.items()
    if age is not None and age >= 65
]

youth_cols = [
    col for col, age in age_map.items()
    if age is not None and 0 <= age <= 14
]

if not elderly_cols:
    st.error("65세 이상 인구 열을 찾을 수 없습니다.")
    st.stop()

if not youth_cols:
    st.error("0~14세 인구 열을 찾을 수 없습니다.")
    st.stop()

grouped["65세이상인구"] = grouped[elderly_cols].sum(axis=1)
grouped["유소년인구"] = grouped[youth_cols].sum(axis=1)

grouped["고령화율"] = np.where(
    grouped["전체인구"] > 0,
    grouped["65세이상인구"] / grouped["전체인구"] * 100,
    np.nan,
)

grouped["유소년비율"] = np.where(
    grouped["전체인구"] > 0,
    grouped["유소년인구"] / grouped["전체인구"] * 100,
    np.nan,
)

# 코드별 중복은 제거합니다.
grouped["시군구코드"] = grouped["시군구코드"].astype(str)
grouped = grouped.drop_duplicates("시군구코드")


# ==================================================
# 7. 전국 지표 카드 계산
# ==================================================
national_total = grouped["전체인구"].sum()

if value_col == "고령화율":
    national_numerator = grouped["65세이상인구"].sum()
else:
    national_numerator = grouped["유소년인구"].sum()

national_rate = (
    national_numerator / national_total * 100
    if national_total > 0
    else np.nan
)

rank_data = grouped.dropna(subset=[value_col]).copy()

if rank_data.empty:
    highest = None
    lowest = None
else:
    highest = rank_data.loc[rank_data[value_col].idxmax()]
    lowest = rank_data.loc[rank_data[value_col].idxmin()]


def percent(value):
    if pd.isna(value):
        return "자료 없음"
    return f"{value:.2f}%"


def make_card(label, value, subtitle):
    return (
        '<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        f'<div class="metric-sub">{subtitle}</div>'
        '</div>'
    )


st.markdown("### 📌 핵심 지표")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        make_card(
            f"전국 {unit_title}",
            percent(national_rate),
            f"{year}년 전국 인구 기준",
        ),
        unsafe_allow_html=True,
    )

with c2:
    if highest is None:
        high_name, high_value = "자료 없음", "자료 없음"
    else:
        high_name = str(highest["시군구"])
        high_value = percent(highest[value_col])

    st.markdown(
        make_card(
            "가장 높은 시군구",
            high_name,
            high_value,
        ),
        unsafe_allow_html=True,
    )

with c3:
    if lowest is None:
        low_name, low_value = "자료 없음", "자료 없음"
    else:
        low_name = str(lowest["시군구"])
        low_value = percent(lowest[value_col])

    st.markdown(
        make_card(
            "가장 낮은 시군구",
            low_name,
            low_value,
        ),
        unsafe_allow_html=True,
    )


# ==================================================
# 8. 지도 범위 설정
# ==================================================
# 경계 파일에 존재하는 시군구 코드
geo_codes = {
    str(feature["properties"].get("코드"))
    for feature in geojson["features"]
    if feature["properties"].get("코드") is not None
}

# 인구 자료와 경계 파일의 코드로 연결합니다.
grouped["시군구코드"] = grouped["시군구코드"].map(normalize_code)

if province == "전국":
    selected_data = grouped.copy()
    selected_features = geojson["features"]

else:
    selected_data = grouped[
        grouped["시도"].astype(str) == province
    ].copy()

    # 경계 파일의 시도 속성도 함께 이용해 해당 시도만 확대합니다.
    province_features = [
        f for f in geojson["features"]
        if str(f["properties"].get("시도", "")) == province
    ]

    # 이름 표기가 서로 다른 경우 코드 집합으로 보완합니다.
    selected_codes = set(selected_data["시군구코드"].dropna())
    province_features = [
        f for f in geojson["features"]
        if (
            str(f["properties"].get("시도", "")) == province
            or str(f["properties"].get("코드", "")) in selected_codes
        )
    ]

    selected_features = province_features

selected_geojson = {
    "type": "FeatureCollection",
    "features": selected_features,
}

# 지도에 사용할 시군구 코드 → 값 / 이름 사전
value_lookup = selected_data.set_index("시군구코드")[value_col].to_dict()
name_lookup = selected_data.set_index("시군구코드")["시군구"].to_dict()

for feature in selected_features:
    props = feature["properties"]
    code = str(props.get("코드", ""))

    value = value_lookup.get(code, np.nan)

    props["지도값"] = (
        None if pd.isna(value) else float(value)
    )
    props["지도이름"] = name_lookup.get(
        code,
        props.get("시군구", "자료 없음"),
    )


# ==================================================
# 9. 단계별 색상 지도
# ==================================================
fig = go.Figure()

# 지표값이 있는 지역을 단계별로 나누어 그립니다.
for i in range(len(breaks) - 1):
    lower = breaks[i]
    upper = breaks[i + 1]

    if i == len(breaks) - 2:
        subset = selected_data[
            selected_data[value_col] >= lower
        ].copy()
    else:
        subset = selected_data[
            (selected_data[value_col] >= lower)
            & (selected_data[value_col] < upper)
        ].copy()

    subset = subset.dropna(subset=[value_col])

    if subset.empty:
        continue

    subset_codes = set(subset["시군구코드"].astype(str))

    features_for_step = [
        f for f in selected_features
        if str(f["properties"].get("코드", "")) in subset_codes
    ]

    if not features_for_step:
        continue

    step_geojson = {
        "type": "FeatureCollection",
        "features": features_for_step,
    }

    fig.add_trace(
        go.Choropleth(
            geojson=step_geojson,
            featureidkey="properties.코드",
            locations=subset["시군구코드"].astype(str),
            z=[1] * len(subset),
            zmin=0,
            zmax=1,
            colorscale=[
                [0, colors[i]],
                [1, colors[i]],
            ],
            showscale=False,
            marker_line_color="white",
            marker_line_width=0.65,
            customdata=np.column_stack(
                [
                    subset["시군구"].astype(str).to_numpy(),
                    subset[value_col].to_numpy(),
                ]
            ),
            hovertemplate=(
                "%{customdata[0]}"
                f"<br>{value_title}: "
                "%{customdata[1]:.2f}%"
                "<extra></extra>"
            ),
            showlegend=False,
        )
    )


# ==================================================
# 10. 자료가 없거나 코드가 맞지 않는 지역은 회색
# ==================================================
drawn_codes = set()

for trace in fig.data:
    if trace.locations is not None:
        drawn_codes.update(str(code) for code in trace.locations)

all_map_codes = {
    str(f["properties"].get("코드", ""))
    for f in selected_features
}

gray_codes = all_map_codes - drawn_codes

gray_features = [
    f for f in selected_features
    if str(f["properties"].get("코드", "")) in gray_codes
]

if gray_features:
    gray_geojson = {
        "type": "FeatureCollection",
        "features": gray_features,
    }

    gray_locations = [
        str(f["properties"]["코드"])
        for f in gray_features
    ]

    gray_names = [
        str(f["properties"].get("시군구", "자료 없음"))
        for f in gray_features
    ]

    fig.add_trace(
        go.Choropleth(
            geojson=gray_geojson,
            featureidkey="properties.코드",
            locations=gray_locations,
            z=[1] * len(gray_locations),
            zmin=0,
            zmax=1,
            colorscale=[
                [0, "#d0d0d0"],
                [1, "#d0d0d0"],
            ],
            showscale=False,
            marker_line_color="white",
            marker_line_width=0.65,
            customdata=np.array(gray_names).reshape(-1, 1),
            hovertemplate=(
                "%{customdata[0]}"
                "<br>자료 없음 또는 코드 불일치"
                "<extra></extra>"
            ),
            showlegend=False,
        )
    )


# 배경 타일 없이 행정구역 경계만 표시합니다.
fig.update_geos(
    visible=False,
    fitbounds="locations",
    showcountries=False,
    showcoastlines=False,
    showland=False,
    showframe=False,
    bgcolor="rgba(0,0,0,0)",
)

fig.update_layout(
    height=760,
    margin=dict(l=0, r=0, t=5, b=5),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

st.markdown(f"### 🗺️ {year}년 {province} {value_title} 지도")
st.plotly_chart(
    fig,
    use_container_width=True,
    config={"displayModeBar": True},
)


# ==================================================
# 11. 색상 범례
# ==================================================
st.markdown("**색상 구간**")

legend_columns = st.columns(len(colors))

for i, col in enumerate(legend_columns):
    with col:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:7px;">
                <span style="
                    display:inline-block;
                    width:18px;
                    height:18px;
                    background:{colors[i]};
                    border:1px solid #aaa;
                    border-radius:4px;">
                </span>
                <span style="font-size:0.83rem;">{labels[i]}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# 경계 파일에 있으나 해당 연도 자료와 연결되지 않은 지역 안내
unmatched_geo = gray_codes

unmatched_population = selected_data[
    ~selected_data["시군구코드"].isin(geo_codes)
]

if unmatched_geo or not unmatched_population.empty:
    st.info(
        "회색 지역은 해당 연도 인구 자료와 경계 파일의 코드가 일치하지 "
        "않거나 지표를 계산할 수 없는 지역입니다. 행정구역 개편 또는 "
        "자료 누락으로 인해 회색으로 표시될 수 있습니다."
    )
else:
    st.caption(
        "지도에 표시된 색은 선택한 지표의 고정 구간을 의미합니다."
    )


# ==================================================
# 12. 시군구별 수치 표
# ==================================================
with st.expander("📋 시군구별 인구 지표 자세히 보기"):
    table = selected_data[
        [
            "시도",
            "시군구",
            "시군구코드",
            "전체인구",
            "65세이상인구",
            "유소년인구",
            "고령화율",
            "유소년비율",
        ]
    ].copy()

    table = table.rename(
        columns={
            "시도": "시도",
            "시군구": "시군구",
            "시군구코드": "시군구 코드",
            "전체인구": "전체 인구",
            "65세이상인구": "65세 이상 인구",
            "유소년인구": "0~14세 인구",
            "고령화율": "고령화율(%)",
            "유소년비율": "유소년 비율(%)",
        }
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )
