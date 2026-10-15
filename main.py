
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #FFF9F2;
}
h1, h2, h3 {
    color: #70452F;
}
.metric-card {
    background-color: #FFFFFF;
    border: 1px solid #EBD8C5;
    border-radius: 12px;
    padding: 18px;
    min-height: 125px;
}
.metric-label {
    color: #785B49;
    font-size: 0.95rem;
    margin-bottom: 8px;
}
.metric-value {
    color: #70452F;
    font-size: 1.8rem;
    font-weight: 700;
}
.warning {
    color: #A13D2D;
    background-color: #FCE8E2;
    border: 1px solid #E7B4A8;
    padding: 7px;
    border-radius: 8px;
    font-weight: 600;
    margin-top: 8px;
}
.summary {
    background-color: #F6E7D8;
    color: #68452F;
    border-radius: 12px;
    padding: 15px;
    margin: 12px 0;
}
</style>
""", unsafe_allow_html=True)

st.title("🏘️ 동네별 인구 피라미드")
st.markdown(
    "우리 동네의 연령별 인구 구성을 살펴보세요. "
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
    # ZIP 압축 CSV 파일을 불러옵니다.
    data = pd.read_csv(DATA_URL, compression="zip")

    # 열 이름에 포함된 불필요한 공백을 제거합니다.
    data.columns = data.columns.astype(str).str.strip()

    # 연도 열을 숫자로 변환합니다.
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
# 3. 최신 연도와 연령별 열 설정
# ==========================================
# 데이터에 실제로 존재하는 가장 최신 연도를 선택합니다.
latest_year = int(df["연도"].max())
df = df[df["연도"] == latest_year].copy()

# 0세부터 100세 이상까지 나이 라벨을 만듭니다.
ages = [f"{i}세" for i in range(101)]
ages[-1] = "100세 이상"

# CSV에 저장된 남녀 인구 열 이름을 만듭니다.
male_cols = [f"남_{age}" for age in ages]
female_cols = [f"여_{age}" for age in ages]

# 필요한 열이 모두 있는지 확인합니다.
required_cols = (
    ["시도", "시군구", "동"] + male_cols + female_cols
)
missing_cols = [
    col for col in required_cols if col not in df.columns
]

if missing_cols:
    st.error("CSV에서 필요한 열을 찾을 수 없습니다.")
    st.write("누락된 열:", missing_cols)
    st.write("실제 열 이름:", df.columns.tolist())
    st.stop()

# 인구 열을 숫자로 변환하고 결측값은 0으로 처리합니다.
for col in male_cols + female_cols:
    df[col] = pd.to_numeric(
        df[col], errors="coerce"
    ).fillna(0)

st.success(f"📅 표시 자료: {latest_year}년")

# ==========================================
# 4. 지역 선택
# ==========================================
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째: 시도
sido_list = sorted(df["시도"].dropna().unique().tolist())

if not sido_list:
    st.error("시도 자료가 없습니다.")
    st.stop()

with col1:
    sido = st.selectbox("시도", sido_list)

# 두 번째: 시군구
sido_df = df[df["시도"] == sido]
sigungu_list = sorted(
    sido_df["시군구"].dropna().unique().tolist()
)

if not sigungu_list:
    st.error("시군구 자료가 없습니다.")
    st.stop()

with col2:
    sigungu = st.selectbox("시군구", sigungu_list)

# 세 번째: 읍·면·동
sigungu_df = sido_df[sido_df["시군구"] == sigungu]
dong_list = sorted(
    sigungu_df["동"].dropna().unique().tolist()
)

if not dong_list:
    st.error("읍·면·동 자료가 없습니다.")
    st.stop()

with col3:
    dong = st.selectbox("읍·면·동", dong_list)

# ==========================================
# 5. 선택한 동네의 인구 계산
# ==========================================
selected = df[
    (df["시도"] == sido)
    & (df["시군구"] == sigungu)
    & (df["동"] == dong)
]

if selected.empty:
    st.warning("선택한 지역의 자료가 없습니다.")
    st.stop()

# 같은 지역의 행이 여러 개라면 연령별로 합산합니다.
population = selected[male_cols + female_cols].sum()

male = np.array(
    [population[col] for col in male_cols], dtype=float
)
female = np.array(
    [population[col] for col in female_cols], dtype=float
)

# 나이별 남녀 합계
total_by_age = male + female

total_male = int(male.sum())
total_female = int(female.sum())
total_population = total_male + total_female

# ==========================================
# 6. 총인구, 평균연령, 고령화율 계산
# ==========================================
# 평균연령은 연령별 인구를 가중치로 계산합니다.
# 100세 이상은 계산 편의를 위해 100세로 간주합니다.
age_numbers = np.arange(101, dtype=float)
population_sum = float(total_by_age.sum())

if population_sum > 0:
    average_age = float(
        np.dot(age_numbers, total_by_age) / population_sum
    )
else:
    average_age = 0.0

# 65세 이상 인구는 65세부터 100세 이상까지 합산합니다.
elderly_population = float(total_by_age[65:].sum())

# 고령화율 = 65세 이상 인구 / 전체 인구 × 100
if population_sum > 0:
    aging_rate = elderly_population / population_sum * 100
else:
    aging_rate = 0.0

# 아이 인구는 0~14세 인구를 기준으로 계산합니다.
children_population = float(total_by_age[:15].sum())

# ==========================================
# 7. 지표 카드 3개
# ==========================================
st.subheader(f"👥 {sido} {sigungu} {dong} 주요 지표")

card1, card2, card3 = st.columns(3)

# 카드 1: 총인구
with card1:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">👥 총인구</div>
            <div class="metric-value">{total_population:,}명</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# 카드 2: 평균연령
with card2:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">🎂 평균연령</div>
            <div class="metric-value">{average_age:.1f}세</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# 카드 3: 고령화율
with card3:
    # 고령화율이 20%를 초과할 때 주의 표시를 추가합니다.
    warning_html = (
        '<div class="warning">⚠️ 고령화율 20% 초과</div>'
        if aging_rate > 20
        else ""
    )

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">👵 고령화율 (65세 이상 비율)</div>
            <div class="metric-value">{aging_rate:.1f}%</div>
            {warning_html}
        </div>
        """,
        unsafe_allow_html=True
    )

# ==========================================
# 8. 인구 피라미드 그래프
# ==========================================
st.subheader("📊 연령별 인구 피라미드")

fig = go.Figure()

# 남성 인구는 음수로 바꾸어 왼쪽에 표시합니다.
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

# 여성 인구는 양수로 오른쪽에 표시합니다.
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

# 가로축을 중앙 기준으로 대칭 설정합니다.
max_pop = max(
    float(male.max()),
    float(female.max())
)
axis_limit = max_pop * 1.1 if max_pop > 0 else 1

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
    range=[-axis_limit, axis_limit],
    zeroline=True,
    zerolinecolor="#A78B76",
    gridcolor="#EDE2D7",
    tickvals=[
        -axis_limit,
        -axis_limit / 2,
        0,
        axis_limit / 2,
        axis_limit
    ],
    # 왼쪽 축의 음수도 양수 인구처럼 표시합니다.
    ticktext=[
        f"{axis_limit:,.0f}",
        f"{axis_limit / 2:,.0f}",
        "0",
        f"{axis_limit / 2:,.0f}",
        f"{axis_limit:,.0f}"
    ]
)

# 나이 순서를 명시적으로 고정합니다.
# categoryarray는 0세부터 100세 이상까지의 순서입니다.
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

st.caption("나이 축 확인: 맨 아래 0세 · 맨 위 100세 이상")

# ==========================================
# 9. 동네 인구 구성 자동 설명
# ==========================================
st.subheader(
    "💬 이 동네는 아이가 많은 편인가요, 어르신이 많은 편인가요?"
)

if total_population <= 0:
    summary = "인구 자료가 없어 연령 구성을 판단하기 어렵습니다."
elif children_population > elderly_population:
    summary = (
        f"이 동네는 0~14세 인구({children_population:,.0f}명)가 "
        f"65세 이상 인구({elderly_population:,.0f}명)보다 많아, "
        "어르신보다 아이 인구가 많은 편입니다."
    )
elif elderly_population > children_population:
    summary = (
        f"이 동네는 65세 이상 인구({elderly_population:,.0f}명)가 "
        f"0~14세 인구({children_population:,.0f}명)보다 많아, "
        "아이보다 어르신 인구가 많은 편입니다."
    )
else:
    summary = (
        f"이 동네는 0~14세 인구와 65세 이상 인구가 "
        f"각각 {children_population:,.0f}명으로 같습니다."
    )

st.markdown(
    f'<div class="summary">{summary}</div>',
    unsafe_allow_html=True
)

# ==========================================
# 10. 연령별 인구 표
# ==========================================
with st.expander("📋 연령별 남녀 인구 표 보기"):
    table = pd.DataFrame({
        "나이": ages,
        "남성 인구": male.astype(int),
        "여성 인구": female.astype(int),
        "전체 인구": total_by_age.astype(int)
    })

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

st.markdown("---")
st.caption(
    "자료: 제공된 연도별 성별 인구 CSV. "
    "평균연령 계산 시 100세 이상은 100세로 간주합니다."
)
