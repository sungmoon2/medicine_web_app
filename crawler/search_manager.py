"""
검색 및 크롤링 관리 모듈
"""
import os
import time
import asyncio
import aiohttp
import hashlib

from urllib.parse import urljoin
from datetime import datetime
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

from config.settings import (
    MAX_PAGES_PER_KEYWORD, CHECKPOINT_INTERVAL,
    CHECKPOINT_DIR, REQUEST_DELAY
)

from config.settings import ROOT_DIR
from bs4 import BeautifulSoup
from utils.helpers import clean_html, generate_safe_filename, save_completed_keyword, load_completed_keywords
from utils.file_handler import save_checkpoint, download_image, save_medicine_json
from utils.logger import get_logger, log_section
from utils.helpers import clean_html, save_completed_keyword, load_completed_keywords, generate_keywords_for_medicines

# 로거 설정
logger = get_logger(__name__)

class SearchManager:
    """
    약품 검색 및 처리를 관리하는 클래스
    """
    def __init__(self, api_client, db_manager, parser):
        """
        검색 관리자 초기화
        
        Args:
            api_client: NaverAPIClient 인스턴스
            db_manager: DatabaseManager 인스턴스
            parser: MedicineParser 인스턴스
        """
        self.api_client = api_client
        self.db_manager = db_manager
        self.parser = parser
        
        # 통계 초기화
        self.stats = {
            'total_searched': 0,
            'medicine_items': 0,
            'saved_items': 0,
            'skipped_items': 0,
            'error_items': 0,
            'api_calls': 0,
            'start_time': datetime.now()
        }
        
        # 완료된 키워드 로드
        self.completed_keywords_file = Path(CHECKPOINT_DIR) / 'completed_keywords.txt'
        self.completed_keywords = set(load_completed_keywords(self.completed_keywords_file))
        
        logger.info(f"검색 관리자 초기화 완료 (완료된 키워드: {len(self.completed_keywords)}개)")
    
    def is_medicine_item(self, url):
        """
        의약품 페이지 유효성 검사
        
        Args:
            url: 검사할 URL
            
        Returns:
            bool: 유효한 의약품 페이지면 True
        """
        try:
            # HTML 내용 가져오기
            html_content = self.api_client.get_html_content(url)
            if not html_content:
                return False
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 1. URL 기본 구조 확인
            if 'terms.naver.com/entry.naver' not in url or 'cid=51000' not in url:
                return False
            
            # 2. 의약품사전 섹션 확인
            section_wrap = soup.find('div', class_='section_wrap')
            if not section_wrap:
                return False
            
            # 3. 제목 영역에서 의약품사전 확인
            headword_title = section_wrap.find('div', class_='headword_title')
            if not headword_title:
                return False
            
            # 4. cite 태그 내 a 태그에서 '의약품사전' 확인
            cite_tag = headword_title.find('p', class_='cite')
            if not cite_tag:
                return False
            
            medicine_dict_link = cite_tag.find('a', string=lambda text: text and '의약품사전' in text)
            if not medicine_dict_link:
                return False
            
            # 5. 추가 검증: 최소한의 의약품 관련 섹션 존재 여부
            size_ct_div = soup.find('div', id='size_ct')
            if not size_ct_div:
                return False
            
            # 섹션 존재 여부 확인
            sections = size_ct_div.find_all('div', class_='section')
            if not sections:
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"페이지 유효성 검사 중 오류: {url}, {e}")
            return False

    def process_medicine_data(self, url):
        """
        의약품 데이터 세부 추출
        
        Args:
            url: 의약품 페이지 URL
            
        Returns:
            dict: 추출된 의약품 데이터
        """
        try:
            # HTML 내용 가져오기
            html_content = self.api_client.get_html_content(url)
            if not html_content:
                logger.warning(f"HTML 내용을 가져올 수 없음: {url}")
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 데이터 저장할 딕셔너리
            medicine_data = {'url': url}
            
            # 1. 한글명과 영문명 추출
            headword_title = soup.find('div', class_='headword_title')
            if headword_title:
                # 한글명 (h2 태그)
                korean_name_tag = headword_title.find('h2', class_='headword')
                if korean_name_tag:
                    medicine_data['korean_name'] = korean_name_tag.get_text(strip=True)
                
                # 영문명 (span 태그)
                english_name_tag = headword_title.find('span', class_='word_txt')
                if english_name_tag:
                    medicine_data['english_name'] = english_name_tag.get_text(strip=True)
            
            # 2. 프로필 정보 추출 (분류, 성상 등)
            profile_div = soup.find('div', class_='tmp_profile')
            if profile_div:
                profile_dts = profile_div.find_all('dt')
                profile_dds = profile_div.find_all('dd')
                
                # 프로필 매핑
                profile_mapping = {
                    '분류': 'category',
                    '구분': 'type',
                    '업체명': 'company',
                    '성상': 'appearance',
                    '보험코드': 'insurance_code',
                    '모양': 'shape',
                    '색깔': 'color',
                    '크기': 'size',
                    '식별표기': 'identification'
                }
                
                for dt, dd in zip(profile_dts, profile_dds):
                    dt_text = dt.get_text(strip=True)
                    dd_text = dd.get_text(strip=True)
                    
                    for key, mapped_key in profile_mapping.items():
                        if key in dt_text:
                            medicine_data[mapped_key] = dd_text
                            break
            
            # 3. 섹션별 상세 내용 추출
            size_ct_div = soup.find('div', id='size_ct')
            if size_ct_div:
                sections = size_ct_div.find_all('div', class_='section')
                for section in sections:
                    h3_tag = section.find('h3')
                    if not h3_tag:
                        continue
                    
                    section_title = h3_tag.get_text(strip=True)
                    content_tag = section.find('p', class_='txt')
                    
                    if content_tag:
                        section_content = content_tag.get_text(strip=True)
                        
                        # 섹션 제목에 따라 키 매핑
                        key = self._map_section_title(section_title)
                        if key:
                            medicine_data[key] = section_content
            
            # 4. 이미지 URL 추출
            try:
                image_url = self._extract_medicine_image_url(soup)
                if image_url:
                    medicine_data['image_url'] = image_url
                    
                    # 이미지 다운로드
                    image_path = download_image(
                        image_url, 
                        medicine_data.get('korean_name', 'unknown_medicine')
                    )
                    if image_path:
                        medicine_data['image_path'] = str(image_path)
            except Exception as e:
                logger.warning(f"이미지 추출 중 오류: {url}, {e}")
            
            # 최소한의 데이터 확인
            if len(medicine_data) <= 1:  # url만 있는 경우
                logger.warning(f"추출된 데이터 없음: {url}")
                return None
            
            return medicine_data
        
        except Exception as e:
            logger.error(f"데이터 추출 중 오류 발생: {url}, {e}")
            return None

    def _extract_medicine_image_url(self, soup):
        """
        의약품 이미지 URL 추출
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            str: 이미지 URL 또는 None
        """
        try:
            # 다양한 이미지 추출 방법 시도
            image_selectors = [
                soup.find('div', class_='img_box').find('img') if soup.find('div', class_='img_box') else None,
                soup.find('img', class_='type_img'),
                soup.find('div', id='size_ct').find('img') if soup.find('div', id='size_ct') else None
            ]
            
            for img_tag in image_selectors:
                if img_tag and 'src' in img_tag.attrs:
                    image_url = img_tag['src']
                    # 상대 경로를 절대 경로로 변환
                    return urllib.parse.urljoin('https://terms.naver.com', image_url)
            
            return None
        
        except Exception as e:
            logger.warning(f"이미지 추출 중 오류: {e}")
            return None
        
    def _map_section_title(self, title):
        """
        섹션 제목을 데이터베이스 키로 매핑
        
        Args:
            title: 섹션 제목
            
        Returns:
            str: 매핑된 키 또는 None
        """
        section_mapping = {
            '성분정보': 'components',
            '효능효과': 'efficacy',
            '주의사항': 'precautions',
            '용법용량': 'dosage',
            '저장방법': 'storage',
            '사용기간': 'period'
        }
        
        for key_word, mapped_key in section_mapping.items():
            if key_word in title:
                return mapped_key
        
        return None
    
    def process_search_item(self, item):
        """
        하나의 검색 결과 항목 처리
        
        Args:
            item: 처리할 검색 결과 항목
            
        Returns:
            dict: 처리 결과 (성공, 실패, 중복, 건너뜀)
        """
        try:
            title = clean_html(item.get('title', ''))
            url = item.get('link', '')
            
            logger.info(f"[시작] 약품 정보 수집: {title} ({url})")
            
            # 이미 처리된 URL인지 확인
            if self.db_manager.is_url_exists(url):
                logger.info(f"[건너뜀] 이미 처리된 URL: {url}")
                return {
                    'success': False,
                    'reason': 'duplicate_url',
                    'url': url
                }
            
            # HTML 내용 가져오기
            try:
                html_content = self.api_client.get_html_content(url)
                if not html_content:
                    logger.warning(f"[실패] HTML 내용을 가져올 수 없음: {url}")
                    return {
                        'success': False,
                        'reason': 'fetch_error',
                        'url': url
                    }
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response.status_code == 404:
                    logger.warning(f"[실패] 페이지를 찾을 수 없음 (404): {url}")
                    return {
                        'success': False,
                        'reason': 'page_not_found',
                        'url': url
                    }
                else:
                    # 다른 HTTP 에러 재발생
                    raise
            
            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 의약품 정보 파싱
            medicine_data = self.parser.parse_medicine_detail(soup, url)
            if not medicine_data:
                logger.warning(f"[실패] 약품 정보를 파싱할 수 없음: {url}")
                return {
                    'success': False,
                    'reason': 'parse_error',
                    'url': url
                }
            
            # 데이터 검증
            validation_result = self.parser.validate_medicine_data(medicine_data)
            if not validation_result['is_valid']:
                logger.warning(f"[실패] 약품 데이터 유효성 검사 실패: {url}, 이유: {validation_result['reason']}")
                return {
                    'success': False,
                    'reason': 'validation_error',
                    'url': url,
                    'validation_result': validation_result
                }
            
            # 추출된 필드 로깅
            field_info = []
            for key in ['korean_name', 'english_name', 'company', 'category']:
                if key in medicine_data and medicine_data[key]:
                    value = medicine_data[key]
                    if len(value) > 30:
                        value = value[:27] + "..."
                    field_info.append(f"{key}: {value}")
            
            logger.info(f"[추출 정보] {', '.join(field_info)}")
            
            # 이미지가 있으면 다운로드
            if medicine_data.get('image_url'):
                image_path = download_image(
                    medicine_data['image_url'], 
                    medicine_data['korean_name']
                )
                if image_path:
                    medicine_data['image_path'] = str(image_path)
                    logger.info(f"[이미지] 다운로드 완료: {image_path}")
            
            # 데이터베이스에 저장
            medicine_id = self.db_manager.save_medicine(medicine_data)
            
            if medicine_id:
                # JSON 파일로도 저장
                json_path = save_medicine_json(medicine_data, medicine_id)
                
                logger.info(f"[성공] 약품 정보 저장 완료: {title} (ID: {medicine_id}, JSON: {os.path.basename(json_path) if json_path else 'None'})")
                return {
                    'success': True,
                    'medicine_id': medicine_id,
                    'korean_name': medicine_data['korean_name'],
                    'url': url,
                    'json_path': json_path
                }
            else:
                logger.warning(f"[실패] 약품 정보 저장 실패: {title}")
                return {
                    'success': False,
                    'reason': 'db_error',
                    'url': url
                }
                    
        except Exception as e:
            logger.error(f"[오류] 검색 항목 처리 중 예외 발생: {str(e)}", exc_info=True)
            return {
                'success': False,
                'reason': 'exception',
                'url': url,
                'error': str(e)
            }
        
    def filter_duplicates(self, items):
        """
        중복 항목 필터링
        
        Args:
            items: 검색 결과 항목 리스트
            
        Returns:
            list: 중복이 제거된 항목 리스트
        """
        filtered_items = []
        seen_urls = set()
        
        for item in items:
            url = item.get('link', '')
            
            # URL이 이미 처리된 경우 건너뜀
            if url in seen_urls:
                continue
            
            # 데이터베이스에 이미 있는지 확인
            if self.db_manager.is_url_exists(url):
                self.stats['skipped_items'] += 1
                continue
            
            # 중복 체크 세트에 추가
            seen_urls.add(url)
            filtered_items.append(item)
        
        return filtered_items
    
    def process_search_results(self, search_results):
        """
        검색 결과 처리
        
        Args:
            search_results: 검색 결과 항목 리스트
            
        Returns:
            tuple: (처리된 항목 수, 의약품 항목 수, 중복 항목 수)
        """
        if not search_results or 'items' not in search_results or not search_results['items']:
            logger.info("[검색 결과] 항목 없음")
            return 0, 0, 0
        
        total_items = len(search_results['items'])
        logger.info(f"[검색 결과] 총 {total_items}개 항목 처리 시작")
        
        medicine_items = []
        
        # 의약품 항목 필터링
        for item in search_results['items']:
            if self.is_medicine_item(item):
                medicine_items.append(item)
        
        medicine_count = len(medicine_items)
        logger.info(f"[검색 결과] 총 {medicine_count}개 의약품 항목 식별됨")
        
        # 중복 항목 필터링
        filtered_items = self.filter_duplicates(medicine_items)
        unique_count = len(filtered_items)
        duplicates = medicine_count - unique_count
        
        if duplicates > 0:
            logger.info(f"[검색 결과] {duplicates}개 중복 항목 제외됨, {unique_count}개 항목 처리 진행")
        
        # 통계 업데이트
        self.stats['total_searched'] += total_items
        self.stats['medicine_items'] += medicine_count
        
        # 결과 처리
        processed_count = 0
        success_count = 0
        error_count = 0
        skip_count = 0
        
        for item in filtered_items:
            result = self.process_search_item(item)
            processed_count += 1
            
            if result['success']:
                success_count += 1
                self.stats['saved_items'] += 1
            else:
                reason = result.get('reason', 'unknown')
                if reason == 'duplicate_url':
                    skip_count += 1
                    self.stats['skipped_items'] += 1
                else:
                    error_count += 1
                    self.stats['error_items'] += 1
        
        logger.info(f"[검색 결과] 처리 완료: {success_count}개 성공, {error_count}개 오류, {skip_count}개 건너뜀, 총 {processed_count}개 처리됨")
        
        return success_count, medicine_count, duplicates
    
    def fetch_keyword_data(self, start_doc_id, end_doc_id, max_pages=None):
        """
        특정 docId 범위의 의약품 데이터 수집
        
        Args:
            start_doc_id: 시작 docId
            end_doc_id: 종료 docId
            max_pages: 최대 페이지 수 (옵션)
            
        Returns:
            tuple: (수집된 항목 수, API 호출 횟수)
        """
        fetched_items = 0
        api_calls = 0
        base_url = "https://terms.naver.com/entry.naver?docId={}&cid=51000&categoryId=51000"
        
        # 페이지네이션 계산
        if max_pages:
            end_doc_id = min(end_doc_id, start_doc_id + max_pages)
        
        for doc_id in range(start_doc_id, end_doc_id + 1):
            # API 한도 체크
            if self.api_client.check_api_limit():
                logger.warning("일일 API 호출 한도에 도달했습니다. 수집 중단")
                break
            
            url = base_url.format(doc_id)
            
            try:
                # 페이지 유효성 확인
                if self.is_medicine_item(url):
                    # 데이터 추출
                    medicine_data = self.process_medicine_data(url)
                    
                    if medicine_data:
                        # 데이터베이스 저장
                        result = self.db_manager.save_medicine(medicine_data)
                        
                        if result:
                            fetched_items += 1
                            api_calls += 1
                    
                    # 요청 간 지연
                    time.sleep(REQUEST_DELAY)
            
            except Exception as e:
                logger.error(f"문서 ID {doc_id} 처리 중 오류: {e}")
        
        return fetched_items, api_calls
    
    async def fetch_keyword_data_async(self, keyword, max_pages=None):
        """
        특정 키워드에 대한 데이터 수집 (비동기 버전)
        
        Args:
            keyword: 검색 키워드
            max_pages: 최대 페이지 수 (None이면 설정값 사용)
            
        Returns:
            tuple: (수집된 항목 수, API 호출 횟수)
        """
        # 비동기 검색 구현
        logger.info(f"비동기 검색은 아직 구현되지 않았습니다. 동기 방식으로 실행: '{keyword}'")
        return await asyncio.to_thread(self.fetch_keyword_data, keyword, max_pages)
    
    def fetch_all_keywords(self, keywords, max_pages=None):
        """
        키워드 리스트 대신 docId 범위로 변경
        
        Args:
            keywords: 키워드 리스트 또는 시작 docId
            max_pages: 최대 페이지 수 또는 종료 docId
            
        Returns:
            dict: 수집 통계
        """
        # 기존 키워드 방식 대응
        if isinstance(keywords, list):
            # 키워드 방식은 더미 구현
            logger.warning("키워드 방식은 더 이상 지원되지 않습니다. docId 범위를 사용하세요.")
            return {
                'total_fetched': 0,
                'total_calls': 0,
                'keywords_processed': 0,
                'keywords_total': len(keywords),
                'duration_seconds': 0.0  # 추가
            }
        
        # docId 범위로 처리
        start_doc_id = keywords  # 첫 번째 인자를 시작 docId로 처리
        
        # 두 번째 인자가 max_pages인지 end_doc_id인지 구분
        if isinstance(max_pages, int):
            # max_pages로 간주
            end_doc_id = start_doc_id + max_pages
        else:
            # end_doc_id로 간주
            end_doc_id = max_pages
        
        # 시작 시간 기록
        start_time = datetime.now()
        self.stats['start_time'] = start_time
        
        log_section(logger, f"docId 범위 수집 시작 ({start_doc_id}~{end_doc_id})")
        
        # 단일 범위에 대해 데이터 수집
        total_fetched = 0
        total_calls = 0
        
        # URL 수집
        valid_urls = self.fetch_medicine_urls(start_doc_id, end_doc_id)
        
        # 데이터 수집
        if valid_urls:
            crawl_stats = self.fetch_medicine_data_from_urls(valid_urls)
            total_fetched = crawl_stats.get('saved_items', 0)
            total_calls = crawl_stats.get('processed_urls', 0)
        
        # 종료 시간 및 소요 시간 계산
        end_time = datetime.now()
        duration = end_time - start_time
        duration_seconds = duration.total_seconds()
        
        # 최종 통계 출력
        log_section(logger, "수집 완료 통계")
        
        logger.info(f"총 수집 항목: {total_fetched}개")
        logger.info(f"총 처리 URL: {total_calls}회")
        logger.info(f"시작 시간: {start_time}")
        logger.info(f"종료 시간: {end_time}")
        logger.info(f"소요 시간: {duration}")
        
        # 최종 통계 반환
        final_stats = {
            'total_fetched': total_fetched,
            'total_calls': total_calls,
            'duration_seconds': duration_seconds,  # 추가
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            **self.stats
        }
        
        return final_stats

    def fetch_medicine_urls(self, start_doc_id, end_doc_id, max_retries=3):
        """
        특정 docId 범위의 의약품 페이지 URL 수집
        
        Args:
            start_doc_id: 시작 docId
            end_doc_id: 종료 docId
            max_retries: 재시도 최대 횟수
            
        Returns:
            list: 유효한 의약품 페이지 URL 리스트
        """
        valid_urls = []
        base_url = "https://terms.naver.com/entry.naver?docId={}&cid=51000&categoryId=51000"
        
        # 통계 초기화
        urls_checked = 0
        valid_url_count = 0
        
        for doc_id in range(start_doc_id, end_doc_id + 1):
            # API 한도 체크
            if self.api_client.check_api_limit():
                logger.warning("일일 API 호출 한도에 도달했습니다. URL 수집 중단")
                break
            
            url = base_url.format(doc_id)
            urls_checked += 1
            
            # 재시도 메커니즘 추가
            for attempt in range(max_retries):
                try:
                    # 페이지 유효성 확인
                    if self.is_medicine_item(url):
                        valid_urls.append(url)
                        valid_url_count += 1
                        break
                except Exception as e:
                    logger.warning(f"URL 확인 시도 실패 ({attempt+1}/{max_retries}): {url}, {e}")
                    
                    # 마지막 재시도에서도 실패하면 건너뜀
                    if attempt == max_retries - 1:
                        logger.error(f"URL 확인 완전 실패: {url}")
                
                # 요청 간 지연
                time.sleep(REQUEST_DELAY)
            
            # 로깅 및 진행상황 표시
            if urls_checked % 100 == 0:
                logger.info(f"진행 상황: {urls_checked}개 URL 확인, 유효 URL {valid_url_count}개")
        
        # 최종 로깅
        logger.info(f"총 {urls_checked}개 URL 중 {valid_url_count}개 유효 URL 수집")
        
        return valid_urls
    
    def fetch_medicine_list_from_search(self, start_page=1, max_pages=100):
        """
        네이버 의약품 검색 페이지에서 의약품 목록 수집
        
        Args:
            start_page: 시작 페이지 번호
            max_pages: 최대 수집 페이지 수 (기본값: 100)
            
        Returns:
            list: 의약품 페이지 URL 리스트
        """
        base_url = "https://terms.naver.com/medicineSearch.naver?page={}"
        medicine_urls = []
        failed_pages = []
        
        # HTML 디버그 폴더 생성 - medicine_web_app 내에 지정
        debug_dir = os.path.join(os.getcwd(), 'debug_html')
        pages_dir = os.path.join(debug_dir, 'pages')
        os.makedirs(debug_dir, exist_ok=True)
        os.makedirs(pages_dir, exist_ok=True)
        logger.info(f"HTML 디버그 파일 저장 경로: {debug_dir}")
        
        # 확실하게 디렉토리 생성
        try:
            os.makedirs(debug_dir, exist_ok=True)
            logger.info(f"HTML 디버그 파일 저장 경로: {debug_dir}")
        except Exception as e:
            logger.error(f"디버그 디렉토리 생성 실패: {e}")
            # 실패 시 현재 디렉토리에 저장
            debug_dir = 'debug_html'
            os.makedirs(debug_dir, exist_ok=True)
        
        # 통계 초기화
        total_pages_checked = 0
        total_medicine_links = 0
        
        # 최대 100페이지로 제한
        end_page = min(start_page + max_pages, 101)  # 1부터 시작하므로 101로 설정
        
        # 첫 번째 패스: 모든 페이지 크롤링 시도
        for page_num in range(start_page, end_page):
            try:
                # 페이지 URL 생성
                url = base_url.format(page_num)
                logger.info(f"페이지 {page_num} 접근 중: {url}")
                
                # HTML 내용 가져오기
                html_content = self.api_client.get_html_content(url)
                
                # HTML 내용 확인
                if not html_content:
                    logger.warning(f"페이지 {page_num}의 HTML 내용을 가져올 수 없음, 나중에 재시도합니다")
                    failed_pages.append(page_num)
                    continue
                
                # 디버깅용 HTML 저장
                try:
                    debug_file = os.path.join(debug_dir, f"page_{page_num}.html")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info(f"페이지 {page_num} HTML 저장됨: {debug_file}")
                except Exception as e:
                    logger.error(f"HTML 저장 실패: {e}")
                
                # BeautifulSoup으로 파싱
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # list_wrap 클래스 찾기 - 여러 선택자 시도
                list_wrap = None
                selectors = [
                    'div.list_wrap',
                    'div#content .list_wrap',
                    '.list_wrap',
                    'ul.content_list',
                    '#content ul'
                ]
                
                for selector in selectors:
                    elements = soup.select(selector)
                    if elements:
                        list_wrap = elements[0]
                        logger.info(f"선택자 '{selector}'로 리스트 요소 찾음")
                        break
                
                if not list_wrap:
                    logger.warning(f"페이지 {page_num}에서 list_wrap을 찾을 수 없음, 나중에 재시도합니다")
                    failed_pages.append(page_num)
                    continue
                
                # li 요소 찾기 - 직접 content_list를 찾지 않고 list_wrap 내의 모든 li 요소 검색
                list_items = list_wrap.find_all('li')
                if not list_items:
                    # 대안으로 모든 a 태그 시도
                    logger.warning(f"페이지 {page_num}에서 리스트 항목을 찾을 수 없음, a 태그로 시도합니다")
                    list_items = list_wrap.find_all('a', href=True)
                    
                    if not list_items:
                        logger.warning(f"페이지 {page_num}에서 링크를 찾을 수 없음, 나중에 재시도합니다")
                        failed_pages.append(page_num)
                        continue
                
                logger.info(f"페이지 {page_num}에서 발견된 리스트 항목 수: {len(list_items)}")
                
                # 각 항목에서 링크 추출
                page_links = []
                
                # li 요소의 경우
                for item in list_items:
                    # 직접 a 태그 찾기
                    link_tag = item.find('a', href=True)
                    
                    # a 태그가 없으면 다음 항목으로
                    if not link_tag:
                        continue
                    
                    href = link_tag['href']
                    
                    # 의약품 링크 필터링 (cid=51000이 있는지 확인)
                    if 'cid=51000' in href and 'entry.naver' in href:
                        # 상대 경로를 절대 경로로 변환
                        full_link = f"https://terms.naver.com{href}" if not href.startswith('http') else href
                        page_links.append(full_link)
                
                # 로깅
                logger.info(f"페이지 {page_num}에서 추출된 의약품 링크 수: {len(page_links)}")
                
                # 링크 추가
                medicine_urls.extend(page_links)
                total_medicine_links += len(page_links)
                total_pages_checked += 1
                
                # 페이지 간 지연
                time.sleep(REQUEST_DELAY)
                    
            except Exception as e:
                logger.error(f"페이지 {page_num} 처리 중 오류: {e}", exc_info=True)
                failed_pages.append(page_num)
        
        # 두 번째 패스: 실패한 페이지 재시도
        if failed_pages:
            logger.info(f"실패한 페이지 {len(failed_pages)}개 재시도 중: {failed_pages}")
            
            for page_num in failed_pages:
                try:
                    # 페이지 URL 생성
                    url = base_url.format(page_num)
                    logger.info(f"[재시도] 페이지 {page_num} 접근 중: {url}")
                    
                    # HTML 내용 가져오기 (재시도 간격 증가)
                    time.sleep(REQUEST_DELAY * 2)  # 더 긴 대기 시간
                    html_content = self.api_client.get_html_content(url)
                    
                    if not html_content:
                        logger.warning(f"[재시도] 페이지 {page_num}의 HTML 내용을 가져올 수 없음, 건너뜁니다")
                        continue
                    
                    # BeautifulSoup으로 파싱
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 모든 a 태그에서 의약품 링크 직접 추출 시도
                    all_links = soup.find_all('a', href=True)
                    
                    page_links = []
                    for link in all_links:
                        href = link['href']
                        if 'cid=51000' in href and 'entry.naver' in href:
                            full_link = f"https://terms.naver.com{href}" if not href.startswith('http') else href
                            page_links.append(full_link)
                    
                    logger.info(f"[재시도] 페이지 {page_num}에서 추출된 의약품 링크 수: {len(page_links)}")
                    
                    # 링크 추가
                    medicine_urls.extend(page_links)
                    total_medicine_links += len(page_links)
                    if len(page_links) > 0:
                        total_pages_checked += 1
                    
                except Exception as e:
                    logger.error(f"[재시도] 페이지 {page_num} 처리 중 오류: {e}", exc_info=True)
        
        # 최종 로깅
        logger.info("의약품 검색 페이지 크롤링 완료")
        logger.info(f"총 확인 페이지: {total_pages_checked}")
        logger.info(f"총 발견 링크: {total_medicine_links}")
        
        # 중복 제거
        unique_urls = list(set(medicine_urls))
        logger.info(f"중복 제거 후 총 링크: {len(unique_urls)}")
        
        return unique_urls
        
    def fetch_medicine_links_from_keywords(self, keywords):
        """
        여러 키워드로 의약품 링크 수집
        
        Args:
            keywords: 검색 키워드 리스트
            
        Returns:
            list: 중복 제거된 의약품 페이지 URL 리스트
        """
        all_urls = set()  # 중복 제거를 위해 집합 사용
        
        for keyword in keywords:
            # 이미 처리된 키워드 건너뛰기
            if keyword in self.completed_keywords:
                logger.info(f"키워드 '{keyword}'는 이미 처리됨, 건너뜀")
                continue
            
            # API로 링크 수집
            urls = self.fetch_medicine_links_from_api(keyword)
            all_urls.update(urls)
            
            # 키워드 처리 완료 표시
            self.completed_keywords.add(keyword)
            save_completed_keyword(keyword, self.completed_keywords_file)
        
        return list(all_urls)

    # main.py의 search_all_keywords 함수 수정
    def search_all_keywords(search_manager, max_pages, limit=None):
        """
        의약품 데이터 수집
        
        Args:
            search_manager: SearchManager 인스턴스
            max_pages: 검색 페이지 수
            limit: 무시됨 (호환성을 위해 유지)
        """
        # 의약품 검색 페이지에서 데이터 수집
        stats = search_manager.fetch_medicine_list_from_search(start_page=1, max_pages=max_pages)
        
        # 결과 출력
        print("\n검색 완료:")
        print(f"총 확인 페이지: {stats['total_pages_checked']}개")
        print(f"총 발견 링크: {stats['total_medicine_links']}개")
        print(f"총 수집 항목: {stats['total_fetched']}개")
        print(f"소요 시간: {stats['duration_seconds']:.1f}초\n")
        
        return stats

    def fetch_medicine_data_from_urls(self, urls, max_items=None, max_retries=3):
        """
        URL 리스트에서 의약품 데이터 수집
        
        Args:
            urls: 의약품 페이지 URL 리스트
            max_items: 최대 수집 항목 수 (옵션)
            max_retries: 재시도 최대 횟수
            
        Returns:
            dict: 수집 통계
        """
        # 통계 초기화
        start_time = datetime.now()
        total_urls = len(urls)
        processed_urls = 0
        saved_items = 0
        failed_urls = []
        
        # 디버그 폴더 설정
        debug_dir = os.path.join(os.getcwd(), 'debug_html')
        extracted_data_dir = os.path.join(debug_dir, 'extracted_data')
        os.makedirs(debug_dir, exist_ok=True)
        os.makedirs(extracted_data_dir, exist_ok=True)
        
        # 최대 수집 항목 제한
        if max_items:
            urls = urls[:max_items]
        
        # 결과 저장 리스트
        medicine_data_list = []
        
        for url in urls:
            # API 한도 체크
            if self.api_client.check_api_limit():
                logger.warning("일일 API 호출 한도에 도달했습니다. 데이터 수집 중단")
                break
            
            # 이미 데이터베이스에 있는지 확인
            if self.db_manager.is_url_exists(url):
                logger.info(f"URL이 이미 처리됨, 건너뜀: {url}")
                processed_urls += 1
                continue
            
            # 재시도 메커니즘 추가
            success = False
            error_message = ""
            
            for attempt in range(max_retries):
                try:
                    # HTML 내용 가져오기
                    html_content = self.api_client.get_html_content(url)
                    
                    if not html_content:
                        logger.warning(f"HTML 내용을 가져올 수 없음: {url}")
                        error_message = "HTML 내용을 가져올 수 없음"
                        continue
                    
                    # BeautifulSoup으로 파싱
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # 의약품 정보 파싱
                    medicine_data = self.parser.parse_medicine_detail(soup, url)
                    
                    if medicine_data:
                        # 추출된 데이터를 HTML 파일로 저장
                        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                        medicine_name = medicine_data.get('korean_name', 'unknown')
                        safe_name = generate_safe_filename(medicine_name, max_length=50)
                        
                        extracted_html = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <title>의약품 데이터: {medicine_name}</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                                h1 {{ color: #333; }}
                                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                                th {{ background-color: #f2f2f2; }}
                                .url {{ word-break: break-all; }}
                                .status {{ color: green; font-weight: bold; }}
                            </style>
                        </head>
                        <body>
                            <h1>의약품 데이터: {medicine_name}</h1>
                            <p class="status">추출 상태: 성공</p>
                            <p class="url">소스 URL: <a href="{url}" target="_blank">{url}</a></p>
                            <table>
                                <tr><th>필드</th><th>값</th></tr>
                        """
                        
                        for field, value in medicine_data.items():
                            if field != 'url' and field != 'data_hash':
                                extracted_html += f"<tr><td>{field}</td><td>{value}</td></tr>\n"
                        
                        extracted_html += """
                            </table>
                        </body>
                        </html>
                        """
                        
                        # 추출 데이터 저장
                        extract_file_path = os.path.join(extracted_data_dir, f"{safe_name}_{url_hash}.html")
                        with open(extract_file_path, 'w', encoding='utf-8') as f:
                            f.write(extracted_html)
                        
                        # 데이터베이스에 저장
                        medicine_id = self.db_manager.save_medicine(medicine_data)
                        
                        if medicine_id:
                            medicine_data_list.append(medicine_data)
                            saved_items += 1
                            success = True
                            break
                        else:
                            error_message = "데이터베이스 저장 실패"
                    else:
                        error_message = "데이터 추출 실패"
                    
                except Exception as e:
                    error_message = str(e)
                    logger.error(f"URL 처리 시도 실패 ({attempt+1}/{max_retries}): {url}, {e}")
                    
                    # 마지막 재시도에서도 실패하면 기록
                    if attempt == max_retries - 1:
                        logger.error(f"URL 처리 완전 실패: {url}")
                
                # 요청 간 지연
                time.sleep(REQUEST_DELAY)
            
            # 처리 결과 기록
            if not success:
                # 실패한 URL과 에러 정보 기록
                failed_urls.append({"url": url, "error": error_message})
                
                # 실패 정보를 HTML로 저장
                if medicine_name is not None:
                    safe_name = generate_safe_filename(medicine_name, max_length=50)
                else:
                    safe_name = "unknown"
                    
                url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                
                failed_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>의약품 데이터 추출 실패: {url}</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        h1 {{ color: #333; }}
                        .error {{ color: red; font-weight: bold; }}
                        .url {{ word-break: break-all; }}
                    </style>
                </head>
                <body>
                    <h1>의약품 데이터 추출 실패</h1>
                    <p class="url">URL: <a href="{url}" target="_blank">{url}</a></p>
                    <p class="error">오류: {error_message}</p>
                    <p>시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p>재시도 횟수: {max_retries}</p>
                </body>
                </html>
                """
                
                # 추출 실패 데이터 저장
                failed_file_path = os.path.join(extracted_data_dir, f"failed_{safe_name}_{url_hash}.html")
                with open(failed_file_path, 'w', encoding='utf-8') as f:
                    f.write(failed_html)
            
            processed_urls += 1
            
            # 진행상황 로깅
            if processed_urls % 10 == 0:
                logger.info(f"진행 상황: {processed_urls}/{total_urls} URL 처리, {saved_items}개 데이터 저장")
        
        # 종료 시간 및 소요 시간 계산
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 실패한 URL을 파일로 저장
        if failed_urls:
            failed_urls_path = os.path.join(debug_dir, "failed_urls.json")
            with open(failed_urls_path, 'w', encoding='utf-8') as f:
                json.dump(failed_urls, f, ensure_ascii=False, indent=2)
            logger.info(f"실패한 URL {len(failed_urls)}개를 {failed_urls_path}에 저장했습니다")
        
        # 최종 통계
        final_stats = {
            'total_urls': total_urls,
            'processed_urls': processed_urls,
            'saved_items': saved_items,
            'failed_urls_count': len(failed_urls),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'failed_urls_file': failed_urls_path if failed_urls else None
        }
        
        # 최종 로깅
        logger.info("데이터 수집 완료")
        logger.info(f"총 URL: {total_urls}, 처리된 URL: {processed_urls}, 저장된 항목: {saved_items}, 실패: {len(failed_urls)}")
        logger.info(f"소요 시간: {duration}")
        
        return final_stats
    
    def find_medicine_docid_range(self, max_search_range=1000, search_step=1, max_retries=3):
        """
        의약품사전의 DocID 범위를 찾는 개선된 메서드
        
        Args:
            max_search_range: 검색할 최대 DocID 범위 (기본값: 1000)
            search_step: 탐색 단계 크기 (기본값: 1)
            max_retries: 각 DocID 검증 시 최대 재시도 횟수
        
        Returns:
            tuple: (시작 DocID, 종료 DocID) 또는 (None, None)
        """
        # 알려진 실제 의약품 DocID를 기본 시작점으로 사용
        base_docid = 2134746  # 확인된 실제 의약품 페이지 DocID
        
        logger.info(f"의약품사전 DocID 범위 탐색 시작 (기준 DocID: {base_docid})")
        
        # 기준 DocID가 유효한지 확인
        if self.is_valid_medicine_docid(base_docid):
            start_docid = base_docid
            logger.info(f"기준 DocID가 유효함: {base_docid}")
        else:
            # 기준 DocID 주변 탐색
            logger.warning(f"기준 DocID {base_docid}가 유효하지 않음, 주변 탐색 시작")
            
            # 앞뒤로 100씩 탐색
            for offset in range(-100, 101):
                if offset == 0:
                    continue
                    
                test_docid = base_docid + offset
                if test_docid > 0 and self.is_valid_medicine_docid(test_docid):
                    start_docid = test_docid
                    logger.info(f"유효한 의약품 DocID 발견: {start_docid}")
                    break
            else:
                # 발견 실패시 다른 범위 탐색
                logger.warning(f"기준 DocID 주변에서 유효한 DocID를 찾지 못함, 폭넓은 탐색 시작")
                
                # 더 넓은 범위 설정
                search_ranges = [
                    (2134000, 2135000, 10),  # 범위 1: 확인된 DocID 주변
                    (2130000, 2140000, 100)  # 범위 2: 더 넓은 범위
                ]
                
                for start_range, end_range, step in search_ranges:
                    for docid in range(start_range, end_range, step):
                        if self.is_valid_medicine_docid(docid):
                            start_docid = docid
                            logger.info(f"유효한 의약품 DocID 발견: {start_docid}")
                            break
                    
                    if 'start_docid' in locals():
                        break
                else:
                    logger.error("유효한 의약품 DocID를 찾을 수 없습니다")
                    return None, None
        
        # 시작 DocID를 기준으로 범위 탐색
        # 1) 이전 DocID 탐색 (역방향)
        found_prev = False
        prev_docid = start_docid
        
        for _ in range(max_search_range):
            test_docid = prev_docid - search_step
            
            try:
                if test_docid <= 0 or not self.is_valid_medicine_docid(test_docid):
                    # 이전 유효 DocID를 찾음
                    logger.info(f"첫 번째 유효한 의약품 DocID: {prev_docid}")
                    found_prev = True
                    break
                
                prev_docid = test_docid
                logger.debug(f"이전 유효 DocID 발견: {prev_docid}")
                
            except Exception as e:
                logger.warning(f"이전 DocID {test_docid} 검증 중 오류: {e}")
                break
            
            # 간격을 두고 요청
            time.sleep(REQUEST_DELAY)
        
        if not found_prev:
            logger.warning(f"첫 번째 의약품 DocID를 찾을 수 없어 현재 DocID 사용: {start_docid}")
            prev_docid = start_docid
        
        # 2) 이후 DocID 탐색 (정방향)
        found_next = False
        next_docid = start_docid
        
        for _ in range(max_search_range):
            test_docid = next_docid + search_step
            
            try:
                if not self.is_valid_medicine_docid(test_docid):
                    # 마지막 유효 DocID를 찾음
                    logger.info(f"마지막 유효한 의약품 DocID: {next_docid}")
                    found_next = True
                    break
                
                next_docid = test_docid
                logger.debug(f"다음 유효 DocID 발견: {next_docid}")
                
            except Exception as e:
                logger.warning(f"다음 DocID {test_docid} 검증 중 오류: {e}")
                break
            
            # 간격을 두고 요청
            time.sleep(REQUEST_DELAY)
        
        if not found_next:
            # 실패 시 임의로 범위 확장
            next_docid = next_docid + 100 
        
        # 최종 범위 반환
        logger.info(f"의약품사전 DocID 범위 결정: {prev_docid} ~ {next_docid}")
        return prev_docid, next_docid

    def is_valid_medicine_docid(self, docid, max_retries=2):
        url = f"https://terms.naver.com/entry.naver?docId={docid}&cid=51000&categoryId=51000"
        
        for attempt in range(max_retries + 1):
            try:
                # HTML 내용 가져오기
                html_content = self.api_client.get_html_content(url)
                if not html_content:
                    return False
                
                # BeautifulSoup으로 파싱
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 간단한 검증: 제목 태그와 의약품 키워드 확인
                title_tag = soup.find('h2', class_='headword')
                if not title_tag:
                    return False
                    
                # cite 태그에서 의약품사전 키워드 확인
                cite_tag = soup.find('p', class_='cite')
                return cite_tag and '의약품사전' in cite_tag.get_text()
                
            except Exception as e:
                if attempt == max_retries:
                    return False
                time.sleep(REQUEST_DELAY)
        
        return False
    
    def fetch_medicine_docid_range(self, start_docid, end_docid, max_items=None):
        """
        DocID 범위의 의약품 데이터 수집
        
        # 추가: search_manager.py에 새로운 메서드로 추가
        # 목적: 특정 DocID 범위의 의약품 데이터 크롤링
        # 사용 방법: find_medicine_docid_range() 메서드와 연계 사용 가능
        
        Args:
            start_docid: 시작 DocID
            end_docid: 종료 DocID
            max_items: 최대 수집 항목 수 (옵션)
        
        Returns:
            dict: 크롤링 통계
        """
        # 시작 시간 기록
        start_time = datetime.now()
        
        # 수집할 URL 생성
        base_url = "https://terms.naver.com/entry.naver?docId={}&cid=51000&categoryId=51000"
        valid_urls = []
        
        # DocID 범위 순회
        for docid in range(start_docid, end_docid + 1):
            # API 호출 한도 체크
            if self.api_client.check_api_limit():
                logger.warning("일일 API 호출 한도에 도달했습니다. 수집 중단")
                break
            
            # 현재 DocID의 URL 생성
            current_url = base_url.format(docid)
            
            try:
                # HTML 내용 가져오기
                html_content = self.api_client.get_html_content(current_url)
                
                if not html_content:
                    logger.warning(f"DocID {docid}의 HTML 내용을 가져올 수 없음")
                    continue
                
                # BeautifulSoup으로 파싱
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 의약품사전 페이지 검증
                if self.parser.is_medicine_dictionary(soup, current_url):
                    valid_urls.append(current_url)
                    
                    # 최대 수집 항목 수 제한
                    if max_items and len(valid_urls) >= max_items:
                        break
            
            except Exception as e:
                logger.error(f"DocID {docid} 처리 중 오류: {e}")
        
        # 수집된 URL로 의약품 데이터 추출
        crawl_stats = self.fetch_medicine_data_from_urls(valid_urls)
        
        # 종료 시간 및 통계 계산
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 최종 통계 업데이트
        crawl_stats.update({
            'start_docid': start_docid,
            'end_docid': end_docid,
            'total_docids_checked': end_docid - start_docid + 1,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds()
        })
        
        return crawl_stats

    # 사용 예시 메서드 추가
    def crawl_medicine_data(self, start_doc_id, end_doc_id, max_items=None):
        """
        의약품 데이터 통합 크롤링 메서드
        
        Args:
            start_doc_id: 시작 docId
            end_doc_id: 종료 docId
            max_items: 최대 수집 항목 수 (옵션)
            
        Returns:
            dict: 크롤링 통계
        """
        # 1. URL 수집
        valid_urls = self.fetch_medicine_urls(start_doc_id, end_doc_id)
        
        # 2. 수집된 URL에서 데이터 추출
        crawl_stats = self.fetch_medicine_data_from_urls(valid_urls, max_items)
        
        return crawl_stats
    
    def fetch_single_url(self, url):
        """
        단일 URL에서 의약품 정보 수집
        
        Args:
            url: 의약품 상세 페이지 URL
            
        Returns:
            dict: 처리 결과
        """
        try:
            logger.info(f"단일 URL 처리: {url}")
            
            # 이미 처리된 URL인지 확인
            if self.db_manager.is_url_exists(url):
                logger.info(f"이미 처리된 URL, 건너뜀: {url}")
                return {
                    'success': False,
                    'reason': 'duplicate_url',
                    'url': url
                }
            
            # HTML 내용 가져오기
            html_content = self.api_client.get_html_content(url)
            if not html_content:
                logger.warning(f"HTML 내용을 가져올 수 없음: {url}")
                return {
                    'success': False,
                    'reason': 'fetch_error',
                    'url': url
                }
            
            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 의약품 정보 파싱
            medicine_data = self.parser.parse_medicine_detail(soup, url)
            if not medicine_data:
                logger.warning(f"약품 정보를 파싱할 수 없음: {url}")
                return {
                    'success': False,
                    'reason': 'parse_error',
                    'url': url
                }
            
            # 데이터 검증
            validation_result = self.parser.validate_medicine_data(medicine_data)
            if not validation_result['is_valid']:
                logger.warning(f"약품 데이터 유효성 검사 실패: {url}, 이유: {validation_result['reason']}")
                return {
                    'success': False,
                    'reason': 'validation_error',
                    'url': url,
                    'validation_result': validation_result
                }
            
            # 이미지가 있으면 다운로드
            if medicine_data.get('image_url'):
                image_path = download_image(
                    medicine_data['image_url'], 
                    medicine_data['korean_name']
                )
                if image_path:
                    medicine_data['image_path'] = str(image_path)
            
            # 데이터베이스에 저장
            medicine_id = self.db_manager.save_medicine(medicine_data)
            
            if medicine_id:
                # JSON 파일로도 저장
                json_path = save_medicine_json(medicine_data, medicine_id)
                
                logger.info(f"약품 정보 저장 완료: {medicine_data['korean_name']} (ID: {medicine_id})")
                return {
                    'success': True,
                    'medicine_id': medicine_id,
                    'korean_name': medicine_data['korean_name'],
                    'url': url,
                    'json_path': json_path
                }
            else:
                logger.warning(f"약품 정보 저장 실패: {medicine_data['korean_name']}")
                return {
                    'success': False,
                    'reason': 'db_error',
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"단일 URL 처리 중 오류 발생: {str(e)}", exc_info=True)
            return {
                'success': False,
                'reason': 'exception',
                'url': url,
                'error': str(e)
            }
    