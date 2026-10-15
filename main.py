
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide"
)

# 따뜻한 색상의 화면 디자인
st.markdown("""
<style>
.stApp {
    background-color: #FFF9F2;
}
h1, h2, h3 {
    color: #70452F;
}
div[data-testid="stMetric"] {
    background-color: white;
    border: 1px solid #EBD8C5;
    padding: 15px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    "전국 읍·면·동의 연령별 남녀 인구를 살펴보세요. "
    "남성은 왼쪽, 여성은 오른쪽에 표시됩니다."
)

# ==========================================
# 2. 데이터 불러오기
# ==========================================
DATA_URL = (
    "https://raw.githubusercontent.com/"
    "boyoung0819/population/main/"
    "population_ts_yearly_gender.zip"
)


@st.cache_data
def load_data():
    # ZIP 압축 CSV를 읽습니다.
    data = pd.read_csv(DATA_URL, compression="zip")

    # 열 이름의 앞뒤 공백을 제거합니다.
    data.columns = data.columns.astype(str).str.strip()

    # 연도를 숫자로 변환합니다.
    data["연도"] = pd.to_numeric(
        data["연도"], errors="coerce"
    )
    data = data.dropna(subset=["연도"]).copy()
    data["연도"] = data["연도"].astype(int)

    # 지역 이름을 문자열로 통일합니다.
    for col in ["시도", "시군구", "동"]:
        data[col] = data[col].astype("string").str.strip()

    return data


try:
    df = load_data()
except Exception as e:
    st.error("인구 데이터를 불러오지 못했습니다.")
    st.code(str(e))
    st.stop()

# ==========================================
# 3. 최신 연도와 나이 열 설정
# ==========================================
# 실제 데이터에 존재하는 가장 최신 연도를 사용합니다.
latest_year = int(df["연도"].max())
df = df[df["연도"] == latest_year].copy()

# 0세부터 100세 이상까지 나이 라벨을 만듭니다.
ages = [f"{i}세" for i in range(101)]
ages[-1] = "100세 이상"

# CSV의 남녀 인구 열 이름을 만듭니다.
male_cols = [f"남_{age}" for age in ages]
female_cols = [f"여_{age}" for age in ages]

# 필요한 열이 있는지 확인합니다.
required_cols = [
    "시도", "시군구", "동"
] + male_cols + female_cols

missing_cols = [
    col for col in required_cols if col not in df.columns
]

if missing_cols:
    st.error("CSV에서 필요한 열을 찾을 수 없습니다.")
    st.write("누락된 열:", missing_cols)
    st.write("실제 CSV 열 이름:", df.columns.tolist())
    st.stop()

# 인구 열을 숫자로 변환합니다.
for col in male_cols + female_cols:
    df[col] = pd.to_numeric(
        df[col], errors="coerce"
    ).fillna(0)

st.success(f"현재 표시 연도: {latest_year}년")

# ==========================================
# 4. 지역 선택: 시도 → 시군구 → 동
# ==========================================
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 드롭다운: 시도
sido_list = sorted(df["시도"].dropna().unique().tolist())

if not sido_list:
    st.error("선택할 수 있는 시도 데이터가 없습니다.")
    st.stop()

with col1:
    sido = st.selectbox("시도", sido_list)

# 두 번째 드롭다운: 선택한 시도의 시군구
sido_df = df[df["시도"] == sido]
sigungu_list = sorted(
    sido_df["시군구"].dropna().unique().tolist()
)

if not sigungu_list:
    st.error("선택한 시도에 시군구 자료가 없습니다.")
    st.stop()

with col2:
    sigungu = st.selectbox("시군구", sigungu_list)

# 세 번째 드롭다운: 선택한 시군구의 동
sigungu_df = sido_df[sido_df["시군구"] == sigungu]
dong_list = sorted(
    sigungu_df["동"].dropna().unique().tolist()
)

if not dong_list:
    st.error("선택한 시군구에 읍·면·동 자료가 없습니다.")
    st.stop()

with col3:
    dong = st.selectbox("읍·면·동", dong_list)

# ==========================================
# 5. 선택한 지역의 인구 계산
# ==========================================
selected = df[
    (df["시도"] == sido)
    & (df["시군구"] == sigungu)
    & (df["동"] == dong)
]

if selected.empty:
    st.warning("선택한 지역의 자료가 없습니다.")
    st.stop()

# 동일 지역에 여러 행이 있으면 연령별 인구를 합산합니다.
population = selected[male_cols + female_cols].sum()

male = np.array(
    [population[col] for col in male_cols], dtype=float
)
female = np.array(
    [population[col] for col in female_cols], dtype=float
)

total_male = int(male.sum())
total_female = int(female.sum())
total_population = total_male + total_female

st.subheader(f"👥 {sido} {sigungu} {dong}")

m1, m2, m3 = st.columns(3)
m1.metric("전체 인구", f"{total_population:,}명")
m2.metric("남성 인구", f"{total_male:,}명")
m3.metric("여성 인구", f"{total_female:,}명")

# ==========================================
# 6. 인구 피라미드 그래프
# ==========================================
fig = go.Figure()

# 남성은 음수로 바꾸어 왼쪽에 표시합니다.
fig.add_trace(go.Bar(
    x=-male,
    y=ages,
    orientation="h",
    name="남성",
    marker_color="#6D91C2",
    customdata=male,
    hovertemplate=(
        "나이: %{y}<br>"
        "남성 인구: %{customdata:,.0f}명"
        "<extra></extra>"
    )
))

# 여성은 양수로 두어 오른쪽에 표시합니다.
fig.add_trace(go.Bar(
    x=female,
    y=ages,
    orientation="h",
    name="여성",
    marker_color="#D98791",
    hovertemplate=(
        "나이: %{y}<br>"
        "여성 인구: %{x:,.0f}명"
        "<extra></extra>"
    )
))

# 남녀 인구를 비교하기 쉽도록 가로축 범위를 대칭으로 설정합니다.
max_pop = max(
    float(male.max()),
    float(female.max())
)
limit = max_pop * 1.1 if max_pop > 0 else 1

fig.update_layout(
    title=f"{dong} 연령별 남녀 인구 피라미드",
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
        x=0.5,
        xanchor="center",
        y=1.03
    ),
    margin=dict(l=100, r=40, t=100, b=70)
)

fig.update_xaxes(
    title_text="인구 (명)",
    range=[-limit, limit],
    zeroline=True,
    zerolinecolor="#A78B76",
    gridcolor="#EDE2D7",
    tickvals=[
        -limit, -limit / 2, 0, limit / 2, limit
    ],
    ticktext=[
        f"{limit:,.0f}",
        f"{limit / 2:,.0f}",
        "0",
        f"{limit / 2:,.0f}",
        f"{limit:,.0f}"
    ]
)

# 중요: 나이 순서를 직접 지정합니다.
# categoryarray가 0세부터 100세 이상까지의 순서를 고정합니다.
# 축을 통째로 뒤집는 옵션은 사용하지 않습니다.
fig.update_yaxes(
    title_text="나이",
    type="category",
    categoryorder="array",
    categoryarray=ages,
    tickmode="array",
    tickvals=ages,
    ticktext=ages,
    showgrid=False
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "나이 축 확인: 맨 아래 0세 · 맨 위 100세 이상"
)

# ==========================================
# 7. 연령별 인구 표
# ==========================================
with st.expander("📋 연령별 남녀 인구 표 보기"):
    table = pd.DataFrame({
        "나이": ages,
        "남성 인구": male.astype(int),
        "여성 인구": female.astype(int),
        "전체 인구": (male + female).astype(int)
    })

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")
st.caption(
    "자료: 제공된 연도별 성별 인구 CSV. "
    "표시된 인구는 원본 데이터 기준입니다."
)
