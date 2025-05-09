# streamlit_app.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time
import plotly.express as px

st.set_page_config(page_title="코인 거래량 변화율 트래커", layout="wide")

# 업비트와 빗썸 API URL
UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"
UPBIT_MARKETS_URL = "https://api.upbit.com/v1/market/all"
BITHUMB_TICKER_URL = "https://api.bithumb.com/public/ticker/ALL_KRW"

def get_upbit_market_codes():
    """업비트의 모든 마켓 코드를 가져옵니다."""
    try:
        response = requests.get(UPBIT_MARKETS_URL)
        markets = response.json()
        krw_markets = [market['market'] for market in markets if market['market'].startswith('KRW-')]
        return krw_markets
    except Exception as e:
        st.error(f"업비트 마켓 코드 가져오기 오류: {e}")
        return []

def get_upbit_volume_data(market_codes):
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
        for ticker in all_tickers:
            # 필요한 정보만 추출
            data = {
                'exchange': '업비트',
                'market': ticker['market'],
                'korean_name': ticker['market'].replace('KRW-', ''),  # 실제로는 별도 API로 한글 이름을 가져와야 함
                'trade_volume': ticker['acc_trade_volume_24h'],
                'trade_volume_prev': ticker['acc_trade_volume'],
                'trade_price': ticker['trade_price'],
                'signed_change_rate': ticker['signed_change_rate'] * 100,  # 퍼센트로 변환
                'timestamp': datetime.fromtimestamp(ticker['timestamp'] / 1000)
            }
            
            # 거래량 변화율 계산 (전일 대비)
            if data['trade_volume_prev'] > 0:
                data['volume_change_rate'] = ((data['trade_volume'] - data['trade_volume_prev']) / data['trade_volume_prev']) * 100
            else:
                data['volume_change_rate'] = 0
                
            volume_data.append(data)
        
        return volume_data
    except Exception as e:
        st.error(f"업비트 거래량 데이터 가져오기 오류: {e}")
        return []

def get_bithumb_volume_data():
    """빗썸의 거래량 데이터를 가져옵니다."""
    try:
        response = requests.get(BITHUMB_TICKER_URL)
        data = response.json()
        
        if data['status'] != '0000':
            st.error(f"빗썸 API 오류: {data['message']}")
            return []
        
        volume_data = []
        for coin, ticker in data['data'].items():
            if coin == 'date':
                continue
                
            # 필요한 정보만 추출
            try:
                volume_24h = float(ticker['volume_1day'])
                volume_prev = float(ticker['volume_7day']) / 7  # 7일 평균으로 대체 (정확한 전일 데이터는 별도 API 필요)
                
                coin_data = {
                    'exchange': '빗썸',
                    'market': f"KRW-{coin}",  # 업비트 형식에 맞춤
                    'korean_name': coin,
                    'trade_volume': volume_24h,
                    'trade_volume_prev': volume_prev,
                    'trade_price': float(ticker['closing_price']),
                    'signed_change_rate': float(ticker['fluctate_rate_24H']),
                    'timestamp': datetime.now()
                }
                
                # 거래량 변화율 계산 (7일 평균 대비)
                if coin_data['trade_volume_prev'] > 0:
                    coin_data['volume_change_rate'] = ((coin_data['trade_volume'] - coin_data['trade_volume_prev']) / coin_data['trade_volume_prev']) * 100
                else:
                    coin_data['volume_change_rate'] = 0
                    
                volume_data.append(coin_data)
            except Exception as e:
                st.error(f"빗썸 {coin} 데이터 처리 오류: {e}")
                continue
        
        return volume_data
    except Exception as e:
        st.error(f"빗썸 거래량 데이터 가져오기 오류: {e}")
        return []

def get_combined_volume_data():
    """업비트와 빗썸의 거래량 데이터를 합쳐서 반환합니다."""
    upbit_markets = get_upbit_market_codes()
    upbit_data = get_upbit_volume_data(upbit_markets)
    bithumb_data = get_bithumb_volume_data()
    
    combined_data = upbit_data + bithumb_data
    
    # 거래량 변화율 기준으로 정렬
    sorted_data = sorted(combined_data, key=lambda x: abs(x['volume_change_rate']), reverse=True)
    
    return sorted_data

# 앱 메인 부분
st.title("코인 거래량 변화율 트래커")
st.caption("업비트와 빗썸의 코인 거래량 변화율을 실시간으로 보여줍니다.")

col1, col2 = st.columns([3, 1])

with col2:
    if st.button("데이터 새로고침", use_container_width=True):
        st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.data = get_combined_volume_data()
        st.success("데이터가 갱신되었습니다!")

if 'data' not in st.session_state or 'last_update' not in st.session_state:
    with st.spinner("데이터를 불러오는 중..."):
        st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.data = get_combined_volume_data()

st.text(f"마지막 업데이트: {st.session_state.last_update}")

# 데이터 가져오기
data = st.session_state.data

# 필터링 옵션
st.subheader("필터 옵션")
col1, col2, col3 = st.columns(3)

with col1:
    exchange_filter = st.multiselect(
        "거래소 선택",
        options=["업비트", "빗썸"],
        default=["업비트", "빗썸"]
    )

with col2:
    min_volume = st.number_input("최소 거래량", min_value=0, value=0)

with col3:
    min_change_rate = st.number_input("최소 변화율 (%)", min_value=0, value=0)

# 데이터 필터링
filtered_data = [
    item for item in data
    if item['exchange'] in exchange_filter
    and item['trade_volume'] >= min_volume
    and abs(item['volume_change_rate']) >= min_change_rate
]

# 상위 10개 코인에 대한 차트 만들기
if filtered_data:
    st.subheader("거래량 변화율 상위 코인")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["차트 보기", "데이터 보기"])
    
    with tab1:
        top10 = filtered_data[:10]
        df_top10 = pd.DataFrame(top10)
        
        # 차트 색상 설정
        df_top10['color'] = df_top10['volume_change_rate'].apply(
            lambda x: '#FF4B4B' if x > 0 else '#4B4BFF'
        )
        
        # 차트 표시
        fig = px.bar(
            df_top10, 
            x='korean_name', 
            y='volume_change_rate',
            color='exchange',
            title="거래량 변화율 상위 10개 코인",
            labels={'korean_name': '코인명', 'volume_change_rate': '거래량 변화율 (%)'},
            height=500
        )
        
        # 차트 스타일 조정
        fig.update_layout(
            xaxis_title="코인명",
            yaxis_title="거래량 변화율 (%)",
            legend_title="거래소",
            font=dict(size=14)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # 테이블용 데이터프레임 생성
        df = pd.DataFrame(filtered_data)
        
        # 열 선택 및 이름 변경
        df = df[['exchange', 'korean_name', 'trade_price', 'signed_change_rate', 'trade_volume', 'volume_change_rate']]
        df.columns = ['거래소', '코인명', '현재가', '24시간 변동률 (%)', '거래량', '거래량 변화율 (%)']
        
        # 컬럼별 형식 지정
        st.dataframe(
            df.style.format({
                '현재가': '{:,.0f} 원',
                '24시간 변동률 (%)': '{:.2f}',
                '거래량': '{:,.0f}',
                '거래량 변화율 (%)': '{:.2f}'
            }).background_gradient(
                cmap='RdYlGn', 
                subset=['거래량 변화율 (%)']
            ),
            use_container_width=True,
            height=600
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
    2. **필터 옵션**을 사용하여 원하는 거래소, 최소 거래량, 최소 변화율을 설정할 수 있습니다.
    3. **차트 보기** 탭에서는 거래량 변화율 상위 10개 코인의 차트를 확인할 수 있습니다.
    4. **데이터 보기** 탭에서는 모든 코인의 데이터를 테이블 형태로 확인할 수 있습니다.
    5. **CSV 다운로드** 버튼을 클릭하여 데이터를 다운로드할 수 있습니다.
    
    ### 참고 사항
    
    - 거래량 변화율은 업비트의 경우 전일 대비, 빗썸의 경우 7일 평균 대비 계산됩니다.
    - 데이터는 자동으로 갱신되지 않으므로, 최신 정보를 보려면 '데이터 새로고침' 버튼을 클릭하세요.
    """)

# 푸터
st.markdown("---")
st.caption("데이터 출처: 업비트 API, 빗썸 API")
st.caption("© 2025 코인 거래량 변화율 트래커")
