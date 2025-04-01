# test_naver_api.py
import requests
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

client_id = os.getenv('NAVER_CLIENT_ID')
client_secret = os.getenv('NAVER_CLIENT_SECRET')

def test_search(query):
    print(f"검색어: {query}")
    
    # 여러 엔드포인트 테스트
    endpoints = ["encyc.json", "webkr.json", "blog.json"]
    
    for endpoint in endpoints:
        url = f"https://openapi.naver.com/v1/search/{endpoint}?query={query}&display=1&start=1"
        
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            status = response.status_code
            print(f"{endpoint} 응답 코드: {status}")
            
            if status == 200:
                print(f"{endpoint} 응답: {response.json()}")
            else:
                print(f"{endpoint} 오류: {response.text}")
                
        except Exception as e:
            print(f"{endpoint} 예외: {str(e)}")
        
        print("-" * 50)

if __name__ == "__main__":
    test_search("타이레놀")
    test_search("소화제")