# streamlit_app.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="코인 거래량 변화율 트래커", layout="wide")

# 업비트 API URL
UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"
UPBIT_MARKETS_URL = "https://api.upbit.com/v1/market/all"

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
            try:
                # 필요한 정보만 추출 (API 응답 구조 변경 가능성 대비한 안전한 접근)
                data = {
                    'exchange': '업비트',
                    'market': ticker.get('market', ''),
                    'korean_name': ticker.get('market', '').replace('KRW-', ''),
                    'trade_volume': ticker.get('acc_trade_volume_24h', 0),
                    'trade_price': ticker.get('trade_price', 0),
                    'signed_change_rate': ticker.get('signed_change_rate', 0) * 100,  # 퍼센트로 변환
                    'timestamp': datetime.now()
                }
                
                # 전일 대비 거래량이 없을 경우 기본값 설정
                prev_volume = ticker.get('acc_trade_volume', 0)
                if 'acc_trade_volume_24h' in ticker and prev_volume > 0:
                    data['volume_change_rate'] = ((data['trade_volume'] - prev_volume) / prev_volume) * 100
                else:
                    data['volume_change_rate'] = 0
                    
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
st.caption("업비트 코인의 거래량 변화율을 실시간으로 보여줍니다.")

col1, col2 = st.columns([3, 1])

with col2:
    if st.button("데이터 새로고침", use_container_width=True):
        st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.data = get_upbit_market_codes()
        st.session_state.volume_data = get_upbit_volume_data(st.session_state.data)
        st.success("데이터가 갱신되었습니다!")

if 'data' not in st.session_state or 'volume_data' not in st.session_state or 'last_update' not in st.session_state:
    with st.spinner("데이터를 불러오는 중..."):
        st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.data = get_upbit_market_codes()
        st.session_state.volume_data = get_upbit_volume_data(st.session_state.data)

st.text(f"마지막 업데이트: {st.session_state.last_update}")

# 데이터 가져오기
volume_data = st.session_state.volume_data

# 필터링 옵션
st.subheader("필터 옵션")
col1, col2 = st.columns(2)

with col1:
    min_volume = st.number_input("최소 거래량", min_value=0, value=0)

with col2:
    min_change_rate = st.number_input("최소 변화율 (%)", min_value=0, value=0)

# 데이터 필터링
filtered_data = [
    item for item in volume_data
    if item['trade_volume'] >= min_volume
    and abs(item['volume_change_rate']) >= min_change_rate
]

# 거래량 변화율로 정렬
sorted_data = sorted(filtered_data, key=lambda x: abs(x['volume_change_rate']), reverse=True)

# 데이터 표시
if sorted_data:
    st.subheader("거래량 변화율 상위 코인")
    
    # 탭 생성
    tab1, tab2 = st.tabs(["차트 보기", "데이터 보기"])
    
    with tab1:
        # 상위 10개 코인
        top10 = sorted_data[:10]
        
        # 차트 데이터 준비
        chart_data = pd.DataFrame({
            '코인명': [item['korean_name'] for item in top10],
            '거래량 변화율': [item['volume_change_rate'] for item in top10]
        })
        
        # 기본 Streamlit 차트 사용 (plotly 대신)
        st.bar_chart(chart_data.set_index('코인명'))
    
    with tab2:
        # 테이블용 데이터프레임 생성
        df = pd.DataFrame(sorted_data)
        
        # 열 선택 및 이름 변경
        df = df[['market', 'korean_name', 'trade_price', 'signed_change_rate', 'trade_volume', 'volume_change_rate']]
        df.columns = ['마켓', '코인명', '현재가', '24시간 변동률 (%)', '거래량', '거래량 변화율 (%)']
        
        # 기본 데이터프레임 표시 (스타일링 제거)
        st.dataframe(df, use_container_width=True, height=600)
        
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
    3. **차트 보기** 탭에서는 거래량 변화율 상위 10개 코인의 차트를 확인할 수 있습니다.
    4. **데이터 보기** 탭에서는 모든 코인의 데이터를 테이블 형태로 확인할 수 있습니다.
    5. **CSV 다운로드** 버튼을 클릭하여 데이터를 다운로드할 수 있습니다.
    """)

# 푸터
st.markdown("---")
st.caption("데이터 출처: 업비트 API")
st.caption("© 2025 코인 거래량 변화율 트래커")
