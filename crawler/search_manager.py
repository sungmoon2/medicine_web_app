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
            
            # 최소한의 데이터 확인
            if len(medicine_data) <= 1:  # url만 있는 경우
                logger.warning(f"추출된 데이터 없음: {url}")
                return None
            
            return medicine_data
        
        except Exception as e:
            logger.error(f"데이터 추출 중 오류 발생: {url}, {e}")
            return None
        
        except Exception as e:
            logger.error(f"데이터 추출 중 오류 발생: {url}, {e}")
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
    
    def fetch_medicine_list_from_search(self, start_page=1, max_pages=10):
        """
        네이버 의약품 검색 페이지에서 의약품 목록 수집
        
        Args:
            start_page: 시작 페이지 번호
            max_pages: 최대 수집 페이지 수
            
        Returns:
            dict: 수집 통계
        """
        base_url = "https://terms.naver.com/medicineSearch.naver?page={}"
        medicine_urls = []
        
        # 통계 초기화
        start_time = datetime.now()
        total_pages_checked = 0
        total_medicine_links = 0
        
        for page_num in range(start_page, start_page + max_pages):
            # API 한도 체크
            if self.api_client.check_api_limit():
                logger.warning("일일 API 호출 한도에 도달했습니다. 수집 중단")
                break
            
            try:
                # 페이지 URL 생성
                url = base_url.format(page_num)
                
                # HTML 내용 가져오기
                html_content = self.api_client.get_html_content(url)
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 의약품 링크 찾기 (네이버 의약품사전 링크)
                medicine_links = soup.find_all('a', href=lambda href: 
                    href and 'terms.naver.com/entry.naver' in href and 'cid=51000' in href)
                
                # 링크 수집
                for link in medicine_links:
                    full_link = f"https://terms.naver.com{link['href']}" if not link['href'].startswith('http') else link['href']
                    medicine_urls.append(full_link)
                
                total_pages_checked += 1
                total_medicine_links += len(medicine_links)
                
                # 페이지 간 지연
                time.sleep(REQUEST_DELAY)
                
                # 로깅
                logger.info(f"페이지 {page_num} 처리: {len(medicine_links)}개 링크 발견")
                
                # 더 이상 의약품 링크가 없으면 중단
                if not medicine_links:
                    logger.info("더 이상 의약품 링크가 없습니다. 수집 중단")
                    break
            
            except Exception as e:
                logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
        
        # 수집된 URL로 데이터 추출
        crawl_stats = self.fetch_medicine_data_from_urls(medicine_urls)
        
        # 최종 통계 계산
        end_time = datetime.now()
        duration = end_time - start_time
        
        final_stats = {
            'total_pages_checked': total_pages_checked,
            'total_medicine_links': total_medicine_links,
            'total_fetched': crawl_stats.get('saved_items', 0),
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds()
        }
        
        logger.info("의약품 검색 페이지 크롤링 완료")
        logger.info(f"총 확인 페이지: {total_pages_checked}")
        logger.info(f"총 발견 링크: {total_medicine_links}")
        logger.info(f"총 수집 항목: {final_stats['total_fetched']}")
        
        return final_stats

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
            
            # 재시도 메커니즘 추가
            for attempt in range(max_retries):
                try:
                    # 데이터 추출
                    medicine_data = self.process_medicine_data(url)
                    
                    if medicine_data:
                        # 데이터베이스에 저장
                        medicine_id = self.db_manager.save_medicine(medicine_data)
                        
                        if medicine_id:
                            medicine_data_list.append(medicine_data)
                            saved_items += 1
                        break
                    else:
                        logger.warning(f"데이터 추출 실패 ({attempt+1}/{max_retries}): {url}")
                
                except Exception as e:
                    logger.error(f"URL 처리 시도 실패 ({attempt+1}/{max_retries}): {url}, {e}")
                    
                    # 마지막 재시도에서도 실패하면 건너뜀
                    if attempt == max_retries - 1:
                        logger.error(f"URL 처리 완전 실패: {url}")
                
                # 요청 간 지연
                time.sleep(REQUEST_DELAY)
            
            processed_urls += 1
            
            # 진행상황 로깅
            if processed_urls % 50 == 0:
                logger.info(f"진행 상황: {processed_urls}/{total_urls} URL 처리, {saved_items}개 데이터 저장")
        
        # 종료 시간 및 소요 시간 계산
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 최종 통계
        final_stats = {
            'total_urls': total_urls,
            'processed_urls': processed_urls,
            'saved_items': saved_items,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds()
        }
        
        # 최종 로깅
        logger.info("데이터 수집 완료")
        logger.info(f"총 URL: {total_urls}, 처리된 URL: {processed_urls}, 저장된 항목: {saved_items}")
        logger.info(f"소요 시간: {duration}")
        
        return final_stats

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
    