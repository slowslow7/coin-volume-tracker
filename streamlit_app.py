# streamlit_app.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

st.set_page_config(page_title="코인 거래량 변화율 트래커", layout="wide")

# 업비트 API URL
UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"
UPBIT_MARKETS_URL = "https://api.upbit.com/v1/market/all"
UPBIT_CANDLE_URL = "https://api.upbit.com/v1/candles/days"  # 일봉 데이터 URL

def get_upbit_market_codes():
    """업비트의 모든 마켓 코드를 가져옵니다."""
    try:
        response = requests.get(UPBIT_MARKETS_URL)
        markets = response.json()
        krw_markets = [market['market'] for market in markets if market['market'].startswith('KRW-')]
        
        # 한글 이름도 함께 가져오기
        market_names = {market['market']: market.get('korean_name', market['market'].replace('KRW-', '')) 
                       for market in markets if market['market'].startswith('KRW-')}
        
        return krw_markets, market_names
    except Exception as e:
        st.error(f"업비트 마켓 코드 가져오기 오류: {e}")
        return [], {}

def get_yesterday_volume(market):
    """특정 마켓의 어제 거래량을 가져옵니다."""
    try:
        # 어제 날짜
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%Y-%m-%d")
        
        params = {
            "market": market,
            "count": 2,  # 최근 2일치 데이터
            "to": yesterday_str + " 23:59:59"  # 어제 마지막 시간
        }
        
        response = requests.get(UPBIT_CANDLE_URL, params=params)
        candles = response.json()
        
        if not candles or len(candles) < 1:
            return 0
        
        # 첫 번째 캔들이 어제 거래량
        return candles[0]['candle_acc_trade_volume']
    except Exception as e:
        st.warning(f"{market} 어제 거래량 가져오기 오류: {e}")
        return 0

def get_upbit_volume_data(market_codes, market_names):
    """업비트의 거래량 데이터를 가져옵니다."""
    try:
        # 한 번에 최대 100개 마켓 정보만 요청 가능하므로 분할 요청
        chunks = [market_codes[i:i+100] for i in range(0, len(market_codes), 100)]
        all_tickers = []
        
        for chunk in chunks:
            params = {"markets": ",".join(chunk)}
            response = requests.get(UPBIT_TICKER_URL, params=params)
            tickers = response.json()
            all_tickers.extend(tickers)
            time.sleep(0.1)  # API 호출 제한 방지를 위한 딜레이
        
        volume_data = []
        
        with st.progress(0.0, text="거래량 데이터 수집 중..."):
            total = len(all_tickers)
            
            for i, ticker in enumerate(all_tickers):
                try:
                    market = ticker.get('market', '')
                    
                    # 진행 상황 업데이트
                    progress = (i + 1) / total
                    st.progress(progress, text=f"거래량 데이터 수집 중... ({i+1}/{total})")
                    
                    # 현재 24시간 거래량 (소수점 제거)
                    today_volume = int(ticker.get('acc_trade_volume_24h', 0))
                    
                    # 어제 거래량 조회 (일봉 API 사용, 소수점 제거)
                    yesterday_volume = int(get_yesterday_volume(market))
                    
                    # 거래량 변화율 계산 (소수점 1자리 반올림)
                    if yesterday_volume > 0:
                        volume_change_rate = round(((today_volume - yesterday_volume) / yesterday_volume) * 100, 1)
                    else:
                        volume_change_rate = 0
                    
                    # 필요한 정보만 추출
                    data = {
                        'exchange': '업비트',
                        'market': market,
                        'korean_name': market_names.get(market, market.replace('KRW-', '')),
                        'today_volume': today_volume,
                        'yesterday_volume': yesterday_volume,
                        'trade_price': ticker.get('trade_price', 0),
                        'signed_change_rate': ticker.get('signed_change_rate', 0) * 100,  # 퍼센트로 변환
                        'volume_change_rate': volume_change_rate,
                        'timestamp': datetime.now()
                    }
                    
                    volume_data.append(data)
                except Exception as e:
                    st.warning(f"업비트 {ticker.get('market', 'unknown')} 데이터 처리 오류: {e}")
                    continue
        
        return volume_data
    except Exception as e:
        st.error(f"업비트 거래량 데이터 가져오기 오류: {e}")
        return []

# 앱 메인 부분
st.title("코인 거래량 변화율 트래커")
st.caption("업비트 코인의 어제 대비 오늘 거래량 변화율을 보여줍니다.")

col1, col2 = st.columns([3, 1])

with col2:
    if st.button("데이터 새로고침", use_container_width=True):
        st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        market_codes, market_names = get_upbit_market_codes()
        st.session_state.volume_data = get_upbit_volume_data(market_codes, market_names)
        st.success("데이터가 갱신되었습니다!")

if 'volume_data' not in st.session_state or 'last_update' not in st.session_state:
    with st.spinner("데이터를 불러오는 중..."):
        st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        market_codes, market_names = get_upbit_market_codes()
        st.session_state.volume_data = get_upbit_volume_data(market_codes, market_names)

st.text(f"마지막 업데이트: {st.session_state.last_update}")

# 데이터 가져오기
volume_data = st.session_state.volume_data

# 필터링 옵션
st.subheader("필터 옵션")
col1, col2, col3 = st.columns(3)

with col1:
    min_volume = st.number_input("최소 거래량", min_value=0, value=1000)

with col2:
    min_change_rate = st.number_input("최소 변화율 (%)", min_value=0, value=10)

with col3:
    sort_by = st.selectbox(
        "정렬 기준",
        options=["거래량 변화율 (절대값)", "거래량 변화율 (양수 우선)", "오늘 거래량"]
    )

# 데이터 필터링
filtered_data = [
    item for item in volume_data
    if item['today_volume'] >= min_volume
    and abs(item['volume_change_rate']) >= min_change_rate
]

# 정렬 적용
if sort_by == "거래량 변화율 (절대값)":
    sorted_data = sorted(filtered_data, key=lambda x: abs(x['volume_change_rate']), reverse=True)
elif sort_by == "거래량 변화율 (양수 우선)":
    sorted_data = sorted(filtered_data, key=lambda x: (-1 if x['volume_change_rate'] > 0 else 1, -abs(x['volume_change_rate'])))
else:  # "오늘 거래량"
    sorted_data = sorted(filtered_data, key=lambda x: x['today_volume'], reverse=True)

# 데이터 표시
if sorted_data:
    st.subheader("거래량 변화율 상위 코인")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["차트 보기", "데이터 보기"])
    
    with tab1:
        # 상위 10개 코인 (변화율 기준 정렬 유지)
        top10 = sorted(sorted_data[:10], key=lambda x: abs(x['volume_change_rate']), reverse=True)
        
        # 차트 데이터 준비 (정렬된 상태 유지)
        chart_data = pd.DataFrame({
            '코인명': [item['korean_name'] for item in top10],
            '거래량 변화율': [item['volume_change_rate'] for item in top10]
        })
        
        # 차트 생성 (인덱스 설정으로 순서 유지)
        chart = st.bar_chart(chart_data.set_index('코인명'))
        
        # 추가 정보 제공
        st.subheader("상위 10개 코인 상세 정보")
        
        # 데이터 테이블 준비
        df_top10 = pd.DataFrame(top10)
        df_top10 = df_top10[['korean_name', 'market', 'trade_price', 'signed_change_rate', 'today_volume', 'yesterday_volume', 'volume_change_rate']]
        df_top10.columns = ['코인명', '마켓', '현재가', '가격변동률 (%)', '오늘 거래량', '어제 거래량', '거래량 변화율 (%)']
        
        # 데이터 형식 지정 (소수점 조정)
        df_top10['가격변동률 (%)'] = df_top10['가격변동률 (%)'].round(1)
        df_top10['오늘 거래량'] = df_top10['오늘 거래량'].astype(int)
        df_top10['어제 거래량'] = df_top10['어제 거래량'].astype(int)
        df_top10['거래량 변화율 (%)'] = df_top10['거래량 변화율 (%)'].round(1)
        
        # 표 떨림 방지를 위해 고정 너비 컨테이너에 표시
        st.container()
        st.dataframe(
            df_top10,
            use_container_width=True,
            height=400,  # 높이 고정
            hide_index=True  # 인덱스 숨김
        )
    
    with tab2:
        # 테이블용 데이터프레임 생성
        df = pd.DataFrame(sorted_data)
        
        # 열 선택 및 이름 변경
        df = df[['market', 'korean_name', 'trade_price', 'signed_change_rate', 'today_volume', 'yesterday_volume', 'volume_change_rate']]
        df.columns = ['마켓', '코인명', '현재가', '가격변동률 (%)', '오늘 거래량', '어제 거래량', '거래량 변화율 (%)']
        
        # 데이터 형식 지정 (소수점 조정)
        df['가격변동률 (%)'] = df['가격변동률 (%)'].round(1)
        df['오늘 거래량'] = df['오늘 거래량'].astype(int)
        df['어제 거래량'] = df['어제 거래량'].astype(int)
        df['거래량 변화율 (%)'] = df['거래량 변화율 (%)'].round(1)
        
        # 기본 데이터프레임 표시 (표 떨림 방지)
        st.container()
        st.dataframe(
            df,
            use_container_width=True,
            height=600,
            hide_index=True  # 인덱스 숨김
        )
        
        # CSV 다운로드 버튼
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "CSV 다운로드",
            csv,
            "coin_volume_data.csv",
            "text/csv",
            key='download-csv'
        )
else:
    st.warning("데이터를 불러올 수 없거나 필터 조건에 맞는 데이터가 없습니다.")

# 사용 방법 안내
with st.expander("📚 사용 방법"):
    st.markdown("""
    ### 사용 방법
    
    1. **데이터 새로고침** 버튼을 클릭하여 최신 데이터를 불러올 수 있습니다.
    2. **필터 옵션**을 사용하여 최소 거래량, 최소 변화율을 설정할 수 있습니다.
    3. **정렬 기준**을 선택하여 다양한 방식으로 데이터를 정렬할 수 있습니다.
    4. **차트 보기** 탭에서는 거래량 변화율 상위 10개 코인의 차트를 확인할 수 있습니다.
    5. **데이터 보기** 탭에서는 모든 코인의 데이터를 테이블 형태로 확인할 수 있습니다.
    6. **CSV 다운로드** 버튼을 클릭하여 데이터를 다운로드할 수 있습니다.
    
    ### 데이터 설명
    
    - **오늘 거래량**: 최근 24시간 동안의 거래량
    - **어제 거래량**: 어제 하루 동안의 거래량 (일봉 데이터 기준)
    - **거래량 변화율**: (오늘 거래량 - 어제 거래량) / 어제 거래량 * 100
    """)

# 푸터
st.markdown("---")
st.caption("데이터 출처: 업비트 API")
st.caption("© 2025 코인 거래량 변화율 트래커")
