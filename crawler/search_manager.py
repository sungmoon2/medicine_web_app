"""
검색 및 크롤링 관리 모듈
"""
import time
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path
from config.settings import (
    MAX_PAGES_PER_KEYWORD, CHECKPOINT_INTERVAL,
    CHECKPOINT_DIR, REQUEST_DELAY
)
from utils.helpers import clean_html, save_completed_keyword, load_completed_keywords
from utils.file_handler import save_checkpoint, download_image, save_medicine_json
from utils.logger import get_logger, log_section

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
    
    def is_medicine_item(self, item):
        """
        검색 결과 항목이 의약품인지 확인
        
        Args:
            item: 검색 결과 항목
            
        Returns:
            bool: 의약품이면 True
        """
        # BeautifulSoup으로 HTML 태그 제거
        title = clean_html(item.get('title', ''))
        description = clean_html(item.get('description', ''))
        
        # 의약품 사전 키워드 체크
        if '의약품사전' not in item.get('link', '') and '의약품사전' not in description:
            return False
        
        # 브랜드 정보 체크
        if any(term in title for term in ['제약사', '제약회사', '(주)', '바이오', '파마', '약품회사']):
            return False
        
        # 용어집/목록 페이지 체크
        if any(term in title for term in ['목록', '종류', '리스트', '분류']):
            return False
        
        # 의약품 형태 체크
        medicine_forms = ['정', '캡슐', '주사', '시럽', '연고', '크림', '겔', '패치', '좌제', '분말']
        
        if any(form in title for form in medicine_forms):
            return True
        
        # 용량 표기 체크
        if any(pattern in title for pattern in ['mg', 'μg', 'g', 'ml', '밀리그램']):
            return True
        
        # URL 패턴 체크
        if '/entry.naver' in item.get('link', '') and 'medicinedic' in item.get('link', ''):
            return True
        
        return False
    
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
            
            logger.info(f"약품 정보 수집: {title} ({url})")
            
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
                
                logger.info(f"약품 정보 저장 완료: {title} (ID: {medicine_id})")
                return {
                    'success': True,
                    'medicine_id': medicine_id,
                    'korean_name': medicine_data['korean_name'],
                    'url': url,
                    'json_path': json_path
                }
            else:
                logger.warning(f"약품 정보 저장 실패: {title}")
                return {
                    'success': False,
                    'reason': 'db_error',
                    'url': url
                }
                
        except Exception as e:
            logger.error(f"검색 항목 처리 중 오류 발생: {str(e)}", exc_info=True)
            return {
                'success': False,
                'reason': 'exception',
                'url': url,
                'error': str(e)
            }
    
    def process_search_results(self, search_results):
        """
        검색 결과 처리
        
        Args:
            search_results: 검색 결과 항목 리스트
            
        Returns:
            tuple: (처리된 항목 수, 의약품 항목 수, 중복 항목 수)
        """
        if not search_results or 'items' not in search_results or not search_results['items']:
            return 0, 0, 0
        
        total_items = len(search_results['items'])
        medicine_items = []
        
        # 의약품 항목 필터링
        for item in search_results['items']:
            if self.is_medicine_item(item):
                medicine_items.append(item)
        
        # 중복 항목 필터링
        filtered_items = self.filter_duplicates(medicine_items)
        
        # 통계 업데이트
        self.stats['total_searched'] += total_items
        self.stats['medicine_items'] += len(medicine_items)
        
        # 결과 처리
        processed_count = 0
        for item in filtered_items:
            result = self.process_search_item(item)
            
            if result['success']:
                processed_count += 1
                self.stats['saved_items'] += 1
            else:
                if result['reason'] == 'duplicate_url':
                    self.stats['skipped_items'] += 1
                else:
                    self.stats['error_items'] += 1
        
        # 중복 항목 수 계산
        duplicates = len(medicine_items) - len(filtered_items)
        
        return processed_count, len(medicine_items), duplicates
    
    def fetch_keyword_data(self, keyword, max_pages=None):
        """
        특정 키워드에 대한 데이터 수집
        
        Args:
            keyword: 검색 키워드
            max_pages: 최대 페이지 수 (None이면 설정값 사용)
            
        Returns:
            tuple: (수집된 항목 수, API 호출 횟수)
        """
        if max_pages is None:
            max_pages = MAX_PAGES_PER_KEYWORD
        
        fetched_items = 0
        api_calls = 0
        
        # 이미 완료된 키워드면 건너뜀
        if keyword in self.completed_keywords:
            logger.info(f"이미 완료된 키워드, 건너뜀: '{keyword}'")
            return 0, 0
        
        log_section(logger, f"키워드 '{keyword}' 검색 시작")
        
        # 예상 결과 수 확인 (API 호출 1회)
        initial_result = self.api_client.search_medicine(keyword, display=1, start=1)
        api_calls += 1
        self.stats['api_calls'] += 1
        
        if not initial_result or 'total' not in initial_result:
            logger.warning(f"키워드 '{keyword}'에 대한 검색 결과가 없거나 API 응답 오류")
            return 0, api_calls
        
        total_results = int(initial_result['total'])
        logger.info(f"키워드 '{keyword}'에 대한 예상 결과 수: {total_results}")
        
        # 페이지네이션 계산
        display = 100  # 한 페이지당 최대 항목 수
        max_start = min(1 + display * (max_pages - 1), 1 + display * ((total_results - 1) // display))
        
        # 각 페이지 처리
        for start in range(1, max_start + 1, display):
            # API 호출 한도 체크
            if self.api_client.check_api_limit():
                logger.warning(f"일일 API 호출 한도에 도달했습니다. 키워드 검색 중단: '{keyword}'")
                break
            
            logger.info(f"'{keyword}' 검색 결과 {start}~{start+display-1} 요청 중...")
            result = self.api_client.search_medicine(keyword, display=display, start=start)
            api_calls += 1
            self.stats['api_calls'] += 1
            
            if not result or 'items' not in result or not result['items']:
                logger.info(f"'{keyword}'에 대한 추가 결과 없음 또는 마지막 페이지 도달")
                break
            
            # 검색 결과 처리
            processed, medicine_count, duplicate_count = self.process_search_results(result)
            fetched_items += processed
            
            logger.info(
                f"처리 완료: {processed}개 항목 추가, {medicine_count}개 의약품 항목 감지, {duplicate_count}개 중복 항목 건너뜀"
            )
            
            # 체크포인트 저장 (CHECKPOINT_INTERVAL 간격으로)
            if self.stats['saved_items'] % CHECKPOINT_INTERVAL == 0 and self.stats['saved_items'] > 0:
                checkpoint_data = {
                    'timestamp': datetime.now().isoformat(),
                    'current_keyword': keyword,
                    'current_start': start + display,
                    'stats': self.stats
                }
                save_checkpoint(checkpoint_data)
            
            # 페이지 간 딜레이
            time.sleep(REQUEST_DELAY)
        
        # 키워드 완료 표시
        self.completed_keywords.add(keyword)
        save_completed_keyword(keyword, self.completed_keywords_file)
        
        logger.info(f"키워드 '{keyword}' 검색 완료: {fetched_items}개 수집, API 호출 {api_calls}회")
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
        여러 키워드에 대한 데이터 수집
        
        Args:
            keywords: 검색 키워드 리스트
            max_pages: 키워드당 최대 페이지 수
            
        Returns:
            dict: 수집 통계
        """
        total_fetched = 0
        total_calls = 0
        
        # 시작 시간 기록
        start_time = datetime.now()
        self.stats['start_time'] = start_time
        
        log_section(logger, f"전체 키워드 수집 시작 (총 {len(keywords)}개)")
        
        # 각 키워드별로 수집
        for i, keyword in enumerate(keywords):
            # API 한도 체크
            if self.api_client.check_api_limit():
                logger.warning(f"일일 API 호출 한도에 도달했습니다. 수집 중단 (처리된 키워드: {i}/{len(keywords)})")
                break
            
            fetched, calls = self.fetch_keyword_data(keyword, max_pages)
            total_fetched += fetched
            total_calls += calls
            
            # 진행상황 로깅
            logger.info(f"키워드 진행: {i+1}/{len(keywords)} ({(i+1)/len(keywords)*100:.1f}%)")
        
        # 종료 시간 및 소요 시간 계산
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 최종 통계 출력
        log_section(logger, "수집 완료 통계")
        
        logger.info(f"총 수집 항목: {total_fetched}개")
        logger.info(f"총 API 호출: {total_calls}회")
        logger.info(f"시작 시간: {start_time}")
        logger.info(f"종료 시간: {end_time}")
        logger.info(f"소요 시간: {duration}")
        
        # 최종 통계 반환
        final_stats = {
            'total_fetched': total_fetched,
            'total_calls': total_calls,
            'keywords_processed': i + 1 if i < len(keywords) else len(keywords),
            'keywords_total': len(keywords),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            **self.stats
        }
        
        return final_stats
    
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