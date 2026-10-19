
import json
import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


# --------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

DATA_URL = (
    "https://raw.githubusercontent.com/"
    "first2022-cyber/contents//main/"
    "population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/"
    "first2022-cyber/contents//main/"
    "sigungu_kr.geojson"
)


# --------------------------------------------------
# 2. 화면 디자인
# --------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background-color: #fbfaf7;
    }

    .main-title {
        font-size: 2.15rem;
        font-weight: 800;
        color: #333333;
        margin-bottom: 0.2rem;
    }

    .sub-title {
        color: #777777;
        font-size: 1rem;
        margin-bottom: 1.3rem;
    }

    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e8e3dc;
        border-radius: 12px;
        padding: 16px;
    }

    .info-box {
        background-color: #ffffff;
        border: 1px solid #e8e3dc;
        border-radius: 12px;
        padding: 15px 18px;
        color: #555555;
        line-height: 1.7;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">🗺️ 전국 고령화 단계구분도</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="sub-title">'
    '2026년 6월 기준 · 시군구별 65세 이상 인구 비율'
    '</div>',
    unsafe_allow_html=True,
)


# --------------------------------------------------
# 3. 인구 데이터 불러오기
# --------------------------------------------------
@st.cache_data(show_spinner="2026년 인구 데이터를 불러오는 중...")
def load_population():
    # 압축 CSV를 판다스로 바로 읽음
    df = pd.read_csv(
        DATA_URL,
        compression="zip",
        dtype={"코드": str},
    )

    # 코드와 연도 형식 정리
    df["코드"] = (
        df["코드"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    # 2026년 자료만 사용
    year_text = (
        df["연도"]
        .astype("string")
        .str.extract(r"(\d{4})", expand=False)
    )
    df = df.loc[year_text == "2026"].copy()

    if df.empty:
        raise ValueError("인구 데이터에서 2026년 자료를 찾지 못했습니다.")

    # '계_'로 시작하는 나이별 총인구 열 찾기
    total_cols = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    if not total_cols:
        raise ValueError("'계_'로 시작하는 인구 열이 없습니다.")

    # 열 이름에서 나이를 숫자로 변환
    # 예: 계_0세 -> 0, 계_65세 -> 65,
    #     계_100세 이상 -> 100
    def get_age(column_name):
        age_text = column_name[2:].replace(" ", "")

        if age_text == "100세이상":
            return 100

        match = re.fullmatch(r"(\d+)세", age_text)
        if match:
            return int(match.group(1))

        return None

    age_cols = [
        col for col in total_cols
        if get_age(col) is not None
    ]

    senior_cols = [
        col for col in age_cols
        if get_age(col) >= 65
    ]

    if not senior_cols:
        raise ValueError("65세 이상 인구 열을 찾지 못했습니다.")

    # 인구 열을 숫자로 변환
    for col in age_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 동 코드의 앞 5자리를 시군구 코드로 사용
    df["시군구코드"] = df["코드"].str[:5]

    # 코드가 없는 행은 집계에서 제외
    df = df.dropna(subset=["시군구코드"])
    df = df.loc[df["시군구코드"].str.len() == 5].copy()

    # 시군구별 전체 인구와 65세 이상 인구 계산
    df["전체인구"] = df[age_cols].sum(axis=1)
    df["65세이상인구"] = df[senior_cols].sum(axis=1)

    # 시군구 코드별 합계
    result = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            전체인구=("전체인구", "sum"),
            **{"65세이상인구": ("65세이상인구", "sum")},
        )
    )

    # 고령화율 계산
    result["고령화율"] = (
        result["65세이상인구"]
        .div(result["전체인구"].where(result["전체인구"] > 0))
        .mul(100)
    )

    result = result.dropna(subset=["고령화율"])

    return result


# --------------------------------------------------
# 4. 시군구 경계 GeoJSON 불러오기
# --------------------------------------------------
@st.cache_data(show_spinner="시군구 경계 지도를 불러오는 중...")
def load_geojson():
    response = requests.get(GEOJSON_URL, timeout=40)
    response.raise_for_status()

    geojson = response.json()

    if "features" not in geojson:
        raise ValueError("GeoJSON에 features가 없습니다.")

    # GeoJSON의 코드도 문자열 5자리로 통일
    # 지역명 대신 코드로 정확하게 연결
    valid_features = []

    for feature in geojson["features"]:
        properties = feature.get("properties", {})
        raw_code = properties.get("코드")

        if raw_code is None:
            continue

        code = str(raw_code).strip()
        code = re.sub(r"\.0$", "", code)

        if not code:
            continue

        code = code.zfill(5)

        properties["코드"] = code
        feature["properties"] = properties

        valid_features.append(feature)

    geojson["features"] = valid_features

    return geojson


# --------------------------------------------------
# 5. 데이터 불러오기 및 오류 안내
# --------------------------------------------------
try:
    population = load_population()
    geojson = load_geojson()

except Exception as error:
    st.error("데이터를 불러오는 중 오류가 발생했습니다.")
    st.exception(error)
    st.info(
        "잠시 후 다시 실행해 보세요. 오류가 반복되면 "
        "데이터 URL과 GitHub 파일 상태를 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 6. GeoJSON의 코드와 지역명 목록 만들기
# --------------------------------------------------
boundary_rows = []

for feature in geojson["features"]:
    properties = feature.get("properties", {})

    code = properties.get("코드")
    name = properties.get("시군구", "")

    if code:
        boundary_rows.append(
            {
                "코드": str(code),
                "시군구": str(name),
            }
        )

boundary_df = pd.DataFrame(
    boundary_rows,
    columns=["코드", "시군구"],
).drop_duplicates(subset=["코드"])


# --------------------------------------------------
# 7. 코드로 인구 자료와 경계 자료 연결
# --------------------------------------------------
population = population.rename(
    columns={"시군구코드": "코드"}
)

population["코드"] = population["코드"].astype(str)
boundary_df["코드"] = boundary_df["코드"].astype(str)

map_df = boundary_df.merge(
    population,
    on="코드",
    how="inner",
    validate="one_to_one",
)

if map_df.empty:
    st.error(
        "인구 데이터와 GeoJSON의 코드가 일치하지 않습니다. "
        "두 파일의 코드 형식을 확인해 주세요."
    )
    st.stop()

# 지도에는 실제로 연결된 시군구만 표시
matched_codes = set(map_df["코드"])

geojson["features"] = [
    feature
    for feature in geojson["features"]
    if str(feature.get("properties", {}).get("코드", ""))
    in matched_codes
]


# --------------------------------------------------
# 8. 전국 통계 요약
# --------------------------------------------------
national_total = map_df["전체인구"].sum()
national_seniors = map_df["65세이상인구"].sum()

national_rate = (
    national_seniors / national_total * 100
    if national_total > 0
    else 0
)

highest = map_df.loc[map_df["고령화율"].idxmax()]
lowest = map_df.loc[map_df["고령화율"].idxmin()]

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "지도에 포함된 시군구",
        f"{len(map_df):,}곳",
    )

with col2:
    st.metric(
        "전국 고령화율",
        f"{national_rate:.2f}%",
    )

with col3:
    st.metric(
        "전국 65세 이상 인구",
        f"{national_seniors:,.0f}명",
    )

st.caption(
    "※ 전국 고령화율은 지도에 연결된 시군구의 인구를 합산해 계산합니다."
)


# --------------------------------------------------
# 9. Plotly 단계구분도
# --------------------------------------------------
st.subheader("시군구별 고령화율")

st.markdown(
    """
    <div class="info-box">
    <b>읽는 방법</b><br>
    색이 연할수록 65세 이상 인구 비율이 낮고,
    색이 진할수록 비율이 높습니다.
    지도 위에 마우스를 올리면 시군구 이름과 고령화율을 확인할 수 있습니다.
    </div>
    """,
    unsafe_allow_html=True,
)

fig = go.Figure(
    data=go.Choropleth(
        geojson=geojson,
        locations=map_df["코드"].tolist(),
        z=map_df["고령화율"].tolist(),
        featureidkey="properties.코드",
        customdata=map_df[["시군구"]].to_numpy(),
        colorscale=[
            [0.00, "#fff5eb"],
            [0.20, "#fdd0a2"],
            [0.40, "#fdae6b"],
            [0.60, "#f16913"],
            [0.80, "#d94801"],
            [1.00, "#7f2704"],
        ],
        zmin=0,
        zmax=max(30, float(map_df["고령화율"].max())),
        marker={
            "line": {
                "color": "#ffffff",
                "width": 0.45,
            }
        },
        colorbar={
            "title": {
                "text": "고령화율 (%)",
            },
            "ticksuffix": "%",
            "thickness": 18,
            "len": 0.75,
        },
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "고령화율: %{z:.2f}%"
            "<extra></extra>"
        ),
    )
)

# 배경 타일 없이 경계와 채색 영역만 표시
fig.update_geos(
    fitbounds="locations",
    visible=False,
    showframe=False,
    showcoastlines=False,
    showcountries=False,
    showland=False,
    showocean=False,
    showlakes=False,
    showrivers=False,
    bgcolor="#fbfaf7",
)

fig.update_layout(
    height=800,
    margin={"l": 0, "r": 0, "t": 10, "b": 0},
    paper_bgcolor="#fbfaf7",
    plot_bgcolor="#fbfaf7",
    font={
        "family": "Arial, sans-serif",
        "color": "#333333",
    },
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "displayModeBar": True,
        "scrollZoom": True,
    },
)


# --------------------------------------------------
# 10. 고령화율이 높은 지역과 낮은 지역
# --------------------------------------------------
st.subheader("지역별 비교")

left, right = st.columns(2)

with left:
    st.markdown("#### 🔴 고령화율이 가장 높은 지역")
    st.metric(
        str(highest["시군구"]),
        f'{highest["고령화율"]:.2f}%',
    )

with right:
    st.markdown("#### 🟡 고령화율이 가장 낮은 지역")
    st.metric(
        str(lowest["시군구"]),
        f'{lowest["고령화율"]:.2f}%',
    )


# --------------------------------------------------
# 11. 시군구별 전체 자료 확인
# --------------------------------------------------
with st.expander("시군구별 고령화율 표 보기"):
    table = map_df[
        ["코드", "시군구", "전체인구", "65세이상인구", "고령화율"]
    ].copy()

    table = table.rename(
        columns={
            "코드": "시군구 코드",
            "전체인구": "전체 인구",
            "65세이상인구": "65세 이상 인구",
            "고령화율": "고령화율 (%)",
        }
    )

    table["고령화율 (%)"] = table["고령화율 (%)"].round(2)

    table = table.sort_values(
        "고령화율 (%)",
        ascending=False,
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    "자료: 제공된 2026년 인구 데이터 및 시군구 경계 GeoJSON"
)
