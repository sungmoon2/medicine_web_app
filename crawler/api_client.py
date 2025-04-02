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
import random

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
    def __init__(self, db_manager=None):
        self.client_id = NAVER_CLIENT_ID
        self.client_secret = NAVER_CLIENT_SECRET
        self.db_manager = db_manager
        self.today_api_calls = 0
        self.session = requests.Session()
        
        # 🔹 세션을 통한 네이버 첫 페이지 접근 → 쿠키 유지
        self.session.get("https://www.naver.com", timeout=5)

        # 🔹 User-Agent 랜덤화
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36"
        ]

        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),  # 🔹 랜덤 User-Agent
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.naver.com',  # 🔹 네이버 메인 페이지를 Referer로 추가
            'Origin': 'https://www.naver.com'  # 🔹 Origin 추가
        })
        
        # 현재 URL 저장 변수 (리다이렉트 추적용)
        self.current_url = None
        
        # 오늘 API 호출 횟수 로드
        self._load_today_api_calls()

    def _random_delay(self, min_delay=1, max_delay=3):
        """요청 간 랜덤 지연 추가 (1~3초 사이)"""
        delay = random.uniform(min_delay, max_delay)
        logger.info(f"랜덤 대기 시간: {delay:.2f}초")
        time.sleep(delay)

    def search_medicine(self, keyword, display=None, start=1):
        # 요청 간 랜덤 지연 추가
        self._random_delay()

        try:
            response = self.session.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
            return response.json()
        except requests.RequestException as e:
            logger.error(f"네이버 API 요청 중 오류 발생: {e}")
            return None
        
    def get_html_content(self, url, follow_redirects=True, max_retries=3):
        # 랜덤 대기 시간 적용
        self._random_delay()

        try:
            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
            return response.text
        except requests.RequestException as e:
            logger.error(f"HTML 페이지 가져오는 중 오류 발생: {e}")
            return None


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
    def get_html_content(self, url, follow_redirects=True, max_retries=3):
        """
        주어진 URL에서 HTML 내용 가져오기 (리다이렉트 처리 개선)
        
        Args:
            url: 가져올 웹페이지 URL
            follow_redirects: 리다이렉트 따라가기 여부
            max_retries: 최대 재시도 횟수
            
        Returns:
            str: 웹페이지 HTML 내용 또는 None (에러 발생 시)
        """
        # API 한도 체크 (HTML 요청도 카운트)
        if self.check_api_limit():
            logger.warning("일일 요청 한도에 도달했습니다")
            return None
        
        # URL 정보 추출
        parsed_url = urllib.parse.urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        session = requests.Session()
        
        # 재시도 메커니즘
        for attempt in range(max_retries):
            try:
                # 요청 헤더 설정 (브라우저처럼 보이도록)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                    "Referer": "https://www.naver.com/",  # 네이버 메인 페이지에서 접근한 것처럼 보이도록 설정
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Referer': domain,
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                # 직접 요청 (리다이렉트 허용)
                response = self.session.get(
                    url, 
                    headers=headers,
                    allow_redirects=follow_redirects,
                    timeout=15
                )
                
                # 실제 URL 저장 (리다이렉트 후)
                self.current_url = response.url
                
                # 상태 코드 확인
                if response.status_code == 200:
                    # 인코딩 처리
                    response.encoding = response.apparent_encoding
                    html_content = response.text
                    
                    # 간단한 HTML 유효성 검사
                    if '<html' in html_content.lower() and len(html_content) > 1000:
                        # 디버그 정보
                        logger.debug(f"HTML 가져오기 성공: URL {url} → {response.url if url != response.url else url}")
                        
                        # API 호출 카운터 업데이트
                        self._update_api_call_count()
                        
                        return html_content
                    else:
                        logger.warning(f"HTML 내용이 유효하지 않음: URL {url}, 길이 {len(html_content)}")
                        # 막힌 페이지 또는 비정상 응답 처리
                        if len(html_content) < 1000:
                            logger.debug(f"짧은 응답 내용: {html_content[:200]}")
                
                # 리다이렉트 처리
                elif response.status_code in (301, 302, 303, 307, 308):
                    if not follow_redirects:
                        logger.info(f"리다이렉트 감지: {url} → {response.headers.get('Location')}")
                        return None
                    else:
                        logger.warning(f"리다이렉트 후에도 성공하지 못함: {url} → {response.url}")
                
                # 404 오류
                elif response.status_code == 404:
                    logger.warning(f"페이지를 찾을 수 없음 (404): {url}")
                    return None
                
                # 다른 오류
                else:
                    logger.warning(f"HTTP 오류: 상태 코드 {response.status_code}, URL {url}, 시도 {attempt+1}/{max_retries}")
                
                # 마지막 시도가 아니면 재시도
                if attempt < max_retries - 1:
                    wait_time = REQUEST_DELAY * (attempt + 1)  # 점진적 대기 시간
                    logger.info(f"{wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"HTML 가져오기 실패: URL {url}, 최대 재시도 횟수 초과")
                    return None
                    
            except requests.RequestException as e:
                logger.error(f"요청 중 오류 발생: {url}, {e}, 시도 {attempt+1}/{max_retries}")
                
                # 마지막 시도가 아니면 재시도
                if attempt < max_retries - 1:
                    wait_time = REQUEST_DELAY * (attempt + 1)  # 점진적 대기 시간
                    logger.info(f"{wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    return None
        
        return None

    def _is_valid_url(self, url):
        """
        URL 유효성 검사
        
        Args:
            url: 검사할 URL
            
        Returns:
            bool: 유효한 URL이면 True
        """
        try:
            result = urllib.parse.urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
        
    def verify_url_is_medicine(self, url):
        """
        URL이 의약품 페이지인지 검증
        
        Args:
            url: 검증할 URL
            
        Returns:
            bool: 의약품 페이지면 True
        """
        try:
            html_content = self.get_html_content(url)
            if not html_content:
                return False
            
            # 간단한 패턴 검사
            patterns = [
                'cid=51000',  # URL에 의약품 카테고리 ID 포함
                '의약품사전',    # 의약품사전 키워드 포함
                'medicine'    # medicine 키워드 포함
            ]
            
            return any(pattern in html_content for pattern in patterns)
            
        except Exception as e:
            logger.error(f"URL 검증 중 오류: {url}, {e}")
            return False