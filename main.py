```python
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide"
)

# 따뜻한 색감의 화면 디자인
st.markdown("""
<style>
    .stApp {
        background-color: #FFF9F2;
    }

    h1, h2, h3 {
        color: #70452F;
    }

    .intro {
        padding: 18px;
        border-radius: 14px;
        background-color: #F6E7D8;
        color: #68452F;
        margin-bottom: 20px;
    }

    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #EBD8C5;
        padding: 16px;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# 2. 데이터 불러오기
# --------------------------------------------------
DATA_URL = (
    "https://raw.githubusercontent.com/"
    "boyoung0819/population/main/"
    "population_ts_yearly_gender.zip"
)


@st.cache_data
def load_data():
    """CSV 압축 파일을 읽고 필요한 자료를 정리합니다."""

    # ZIP 주소를 read_csv에 직접 전달하면 압축을 자동으로 풉니다.
    df = pd.read_csv(DATA_URL, compression="zip")

    # 열 이름에 불필요한 공백이 있을 경우 제거합니다.
    df.columns = df.columns.astype(str).str.strip()

    # 연도 열이 숫자로 처리되도록 변환합니다.
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")

    # 연도가 없는 행은 제외합니다.
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    # 지역 이름의 앞뒤 공백을 제거합니다.
    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].astype("string").str.strip()

    return df


# 데이터 로딩 중 오류가 생기면 원인을 안내합니다.
try:
    df = load_data()
except Exception as e:
    st.error("인구 데이터를 불러오지 못했습니다.")
    st.info(
        "인터넷 연결과 데이터 주소를 확인한 뒤 "
        "잠시 후 다시 실행해 주세요."
    )
    st.exception(e)
    st.stop()


# --------------------------------------------------
# 3. 최신 연도 선택
# --------------------------------------------------
# 데이터에 실제로 존재하는 가장 큰 연도를 선택합니다.
latest_year = int(df["연도"].max())

# 최신 연도 자료만 남깁니다.
latest_df = df[df["연도"] == latest_year].copy()

# 연령별 남녀 인구 열 이름을 만듭니다.
# 예: 남_0세, 여_0세, ..., 남_100세 이상, 여_100세 이상
age_labels = [f"{age}세" for age in range(101)]
age_labels[-1] = "100세 이상"

male_cols = [f"남_{age}" for age in age_labels]
female_cols = [f"여_{age}" for age in age_labels]

# 실제 데이터에 연령별 인구 열이 있는지 확인합니다.
required_cols = ["시도", "시군구", "동"] + male_cols + female_cols
missing_cols = [col for col in required_cols if col not in latest_df.columns]

if missing_cols:
    st.error(
        "데이터에서 필요한 열을 찾지 못했습니다. "
        "CSV의 열 이름을 확인해 주세요."
    )
    st.write("찾을 수 없는 열:", missing_cols)
    st.stop()

# 인구 데이터가 숫자로 처리되도록 변환합니다.
# 변환할 수 없는 값과 결측값은 0으로 처리합니다.
for col in male_cols + female_cols:
    latest_df[col] = pd.to_numeric(
        latest_df[col], errors="coerce"
    ).fillna(0)


# --------------------------------------------------
# 4. 제목과 소개
# --------------------------------------------------
st.title("🏘️ 동네별 인구 피라미드")

st.markdown(
    f"""
    <div class="intro">
        <b>{latest_year}년 최신 자료</b>를 바탕으로
        우리 동네의 연령별 인구 구성을 살펴보세요.<br>
        남성 인구는 왼쪽, 여성 인구는 오른쪽에 표시됩니다.
    </div>
    """,
    unsafe_allow_html=True
)

st.caption(
    "자료: 제공된 전국 읍·면·동 연도별 성별 인구 CSV"
)


# --------------------------------------------------
# 5. 지역 선택 드롭다운 3개
# --------------------------------------------------
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 드롭다운: 시도
sido_list = sorted(
    latest_df["시도"].dropna().unique().tolist()
)

with col1:
    selected_sido = st.selectbox(
        "① 시도",
        options=sido_list,
        index=0
    )

# 선택한 시도에 해당하는 자료만 추립니다.
sido_df = latest_df[latest_df["시도"] == selected_sido]

# 두 번째 드롭다운: 시군구
sigungu_list = sorted(
    sido_df["시군구"].dropna().unique().tolist()
)

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        options=sigungu_list,
        index=0
    )

# 선택한 시군구에 해당하는 자료만 추립니다.
sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
]

# 세 번째 드롭다운: 동
dong_list = sorted(
    sigungu_df["동"].dropna().unique().tolist()
)

with col3:
    selected_dong = st.selectbox(
        "③ 읍·면·동",
        options=dong_list,
        index=0
    )


# --------------------------------------------------
# 6. 선택한 동네의 인구 자료 추출
# --------------------------------------------------
# 세 가지 지역 조건이 모두 일치하는 행을 찾습니다.
selected_rows = latest_df[
    (latest_df["시도"] == selected_sido)
    & (latest_df["시군구"] == selected_sigungu)
    & (latest_df["동"] == selected_dong)
]

if selected_rows.empty:
    st.warning("선택한 지역의 인구 자료가 없습니다.")
    st.stop()

# 같은 지역이 여러 행에 나뉘어 있다면 연령별 인구를 합산합니다.
# 숫자 열만 합산하여 지역 인구를 계산합니다.
selected_row = selected_rows[male_cols + female_cols].sum()

# 연령 순서대로 남녀 인구를 각각 추출합니다.
male_population = np.array(
    [selected_row[col] for col in male_cols],
    dtype=float
)

female_population = np.array(
    [selected_row[col] for col in female_cols],
    dtype=float
)

# 남성은 왼쪽에 표시하도록 음수로 변환합니다.
male_population_left = -male_population

# 전체 인구를 계산합니다.
total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# --------------------------------------------------
# 7. 인구 요약 정보
# --------------------------------------------------
st.subheader("👥 인구 한눈에 보기")

st.markdown(
    f"**{selected_sido} {selected_sigungu} {selected_dong}**"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "전체 인구",
    f"{total_population:,}명"
)

metric2.metric(
    "남성 인구",
    f"{total_male:,}명"
)

metric3.metric(
    "여성 인구",
    f"{total_female:,}명"
)


# --------------------------------------------------
# 8. 인구 피라미드 가로 막대그래프
# --------------------------------------------------
st.subheader("📊 연령별 인구 피라미드")

fig = go.Figure()

# 남성 막대: 음수이므로 중앙의 0을 기준으로 왼쪽에 나타납니다.
fig.add_trace(
    go.Bar(
        x=male_population_left,
        y=age_labels,
        orientation="h",
        name="남성",
        marker_color="#6D91C2",
        hovertemplate=(
            "나이: %{y}<br>"
            "남성 인구: %{customdata:,.0f}명"
            "<extra></extra>"
        ),
        customdata=male_population
    )
)

# 여성 막대: 양수이므로 중앙의 0을 기준으로 오른쪽에 나타납니다.
fig.add_trace(
    go.Bar(
        x=female_population,
        y=age_labels,
        orientation="h",
        name="여성",
        marker_color="#D98791",
        hovertemplate=(
            "나이: %{y}<br>"
            "여성 인구: %{x:,.0f}명"
            "<extra></extra>"
        )
    )
)

# 가로축의 좌우 범위를 대칭으로 설정합니다.
# 그래프 중앙을 기준으로 남녀 인구를 비교하기 쉽습니다.
max_population = max(
    float(male_population.max()) if len(male_population) else 0,
    float(female_population.max()) if len(female_population) else 0
)

# 모든 값이 0인 경우에도 그래프가 정상적으로 표시되게 합니다.
axis_limit = max_population * 1.15 if max_population > 0 else 1

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 남녀 인구",
        "x": 0.5,
        "xanchor": "center"
    },
    barmode="overlay",
    bargap=0.12,
    height=1250,
    plot_bgcolor="#FFFCF8",
    paper_bgcolor="#FFFCF8",
    font=dict(
        family="Arial, sans-serif",
        size=12,
        color="#5D4638"
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.01,
        xanchor="center",
        x=0.5
    ),
    margin=dict(l=100, r=45, t=100, b=70)
)

# 가로축: 남성은 음수로 저장했지만 눈금은 양수로 보이게 합니다.
fig.update_xaxes(
    title_text="인구 (명)",
    range=[-axis_limit, axis_limit],
    tickmode="array",
    tickvals=[
        -axis_limit,
        -axis_limit * 0.5,
        0,
        axis_limit * 0.5,
        axis_limit
    ],
    ticktext=[
        f"{axis_limit:,.0f}",
        f"{axis_limit * 0.5:,.0f}",
        "0",
        f"{axis_limit * 0.5:,.0f}",
        f"{axis_limit:,.0f}"
    ],
    zeroline=True,
    zerolinecolor="#A78B76",
    zerolinewidth=1.5,
    gridcolor="#EDE2D7"
)

# --------------------------------------------------
# 9. 나이 축 순서 고정 (중요!)
# --------------------------------------------------
# categoryarray에 0세부터 100세 이상까지 순서대로 지정합니다.
# categoryorder="array"로 이 순서를 그대로 사용합니다.
# 축을 뒤집는 옵션(autorange="reversed")은 사용하지 않습니다.
fig.update_yaxes(
    title_text="나이",
    type="category",
    categoryorder="array",
    categoryarray=age_labels,
    tickmode="array",
    tickvals=age_labels,
    ticktext=age_labels,
    showgrid=False
)

# 최종적으로 0세가 맨 아래, 100세 이상이 맨 위인지 확인할 수 있도록
# 축에 전달한 나이 순서를 화면 아래에 안내합니다.
st.plotly_chart(
    fig,
    use_container_width=True,
    config={"displayModeBar": True}
)

st.caption(
    "나이 축 순서 확인: 아래쪽 0세 → 위쪽 100세 이상"
)


# --------------------------------------------------
# 10. 연령별 인구 표
# --------------------------------------------------
with st.expander("연령별 남녀 인구 표 보기"):
    population_table = pd.DataFrame({
        "나이": age_labels,
        "남성 인구": male_population.astype(int),
        "여성 인구": female_population.astype(int),
        "전체 인구": (
            male_population + female_population
        ).astype(int)
    })

    st.dataframe(
        population_table,
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")
st.caption(
    "※ 인구 수는 제공된 데이터 기준입니다. "
    "자료의 갱신 시점과 행정구역 표기에 따라 결과가 달라질 수 있습니다."
)
```
