"""
네이버 API 호출 클라이언트
"""
import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
import requests
from datetime import datetime
from config.settings import (
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, 
    REQUEST_DELAY, MAX_RETRIES,
    DAILY_API_LIMIT, SEARCH_DEFAULTS
)
from utils.helpers import retry
from utils.logger import get_logger

# 로거 설정
logger = get_logger(__name__)

class NaverAPIClient:
    """
    네이버 Open API 호출을 담당하는 클라이언트 클래스
    """
    def __init__(self, db_manager=None):
        """
        네이버 API 클라이언트 초기화
        
        Args:
            db_manager: 데이터베이스 매니저 (API 호출 카운트 저장용)
        """
        self.client_id = NAVER_CLIENT_ID
        self.client_secret = NAVER_CLIENT_SECRET
        self.db_manager = db_manager
        self.today_api_calls = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 오늘 API 호출 횟수 로드
        self._load_today_api_calls()
        
        logger.info(f"네이버 API 클라이언트 초기화 완료 (금일 API 호출 수: {self.today_api_calls})")

    def _load_today_api_calls(self):
        """오늘의 API 호출 횟수 로드"""
        if self.db_manager:
            # 데이터베이스에서 API 호출 횟수 가져오기
            today = datetime.now().strftime('%Y-%m-%d')
            count = self.db_manager.get_api_call_count(today)
            if count is not None:
                self.today_api_calls = count
        else:
            self.today_api_calls = 0
            
    def _update_api_call_count(self, count=1):
        """
        API 호출 횟수 업데이트
        
        Args:
            count: 증가시킬 호출 횟수
        
        Returns:
            int: 업데이트 후 오늘의 총 API 호출 횟수
        """
        self.today_api_calls += count
        
        if self.db_manager:
            # 데이터베이스에 API 호출 횟수 업데이트
            today = datetime.now().strftime('%Y-%m-%d')
            self.db_manager.update_api_call_count(today, self.today_api_calls)
        
        return self.today_api_calls
    
    def check_api_limit(self):
        """
        API 호출 한도에 도달했는지 확인
        
        Returns:
            bool: API 호출 한도에 도달했으면 True, 아니면 False
        """
        return self.today_api_calls >= DAILY_API_LIMIT
    
    @retry(max_tries=MAX_RETRIES, delay_seconds=REQUEST_DELAY, backoff_factor=2, 
       exceptions=(requests.RequestException, urllib.error.URLError))
    def search_medicine(self, keyword, display=None, start=1):
        """
        네이버 API를 사용하여 약품 검색
        
        Args:
            keyword: 검색 키워드 
            display: 한 번에 가져올 결과 수 (최대 100)
            start: 검색 시작 위치
            
        Returns: 
            dict: API 응답 데이터 또는 None (에러 발생 시)
        """
        if display is None:
            display = SEARCH_DEFAULTS['display']
            
        # 기본값 확인
        display = min(display, 100)  # 최대 100개까지만 가능
        
        # API 한도 체크
        if self.check_api_limit():
            logger.warning(f"일일 API 호출 한도({DAILY_API_LIMIT}회)에 도달했습니다.")
            return None
        
        # 검색어 구성
        search_query = f"{keyword} 의약품"
        encoded_query = urllib.parse.quote(search_query)
        
        # 'encyclop.json' 대신 'encyc.json' 사용
        url = f"https://openapi.naver.com/v1/search/encyc.json?query={encoded_query}&display={display}&start={start}"
        
        # 요청 헤더 설정
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        
        logger.info(f"API 요청: 키워드='{keyword}', display={display}, start={start}")
        
        try:
            # API 요청
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # JSON 파싱
            result = response.json()
            
            # 결과 정보 로깅
            if 'total' in result:
                logger.info(f"API 검색 결과: 총 {result['total']}개 항목 중 {len(result.get('items', []))}개 반환됨")
            else:
                logger.warning(f"API 응답에 'total' 필드가 없음")
            
            # API 호출 카운터 업데이트
            self._update_api_call_count()
            
            # 요청 간 딜레이 추가
            time.sleep(REQUEST_DELAY)
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"API 응답을 JSON으로 파싱할 수 없음: {e}")
            raise
            
        except requests.RequestException as e:
            logger.error(f"API 요청 중 오류 발생: {e}")
            
            # 오류 상세 정보 로깅
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"오류 상태 코드: {e.response.status_code}")
                logger.error(f"오류 응답 내용: {e.response.text}")
            
            raise
    
    @retry(max_tries=3, delay_seconds=1, exceptions=(requests.RequestException,))
    def get_html_content(self, url):
        """
        주어진 URL에서 HTML 내용 가져오기
        
        Args:
            url: 가져올 웹페이지 URL
            
        Returns:
            str: 웹페이지 HTML 내용 또는 None (에러 발생 시)
        """
        try:
            logger.debug(f"HTML 내용 요청: {url}")
            
            # 요청 헤더 설정
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': 'https://search.naver.com/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            # 404 오류는 특별히 처리하여 retry하지 않음
            if response.status_code == 404:
                logger.error(f"URL 접속 중 오류 발생: 404 Client Error: 404 for url: {url}")
                # retry 데코레이터가 감싸도 재시도하지 않도록 HTTP 오류 발생시킴
                response.raise_for_status()
            
            response.raise_for_status()
            
            # 인코딩 확인 및 설정
            if response.encoding.lower() != 'utf-8':
                response.encoding = 'utf-8'
            
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"URL 접속 중 오류 발생: {e}")
            raise