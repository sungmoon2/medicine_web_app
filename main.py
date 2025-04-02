#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
네이버 의약품 정보 크롤러 메인 스크립트
"""
import os
import sys
import time
import argparse
import json
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from config.settings import (
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, 
    MAX_PAGES_PER_KEYWORD, CHECKPOINT_DIR, 
    LOG_LEVEL, LOG_FILE
)
from crawler.api_client import NaverAPIClient
from crawler.parser import MedicineParser
from crawler.search_manager import SearchManager
from db.db_manager import DatabaseManager
from utils.helpers import create_keyword_list, generate_keywords_for_medicines
from utils.file_handler import save_checkpoint, load_checkpoint
from utils.logger import get_logger, log_section, log_exception

import logging

# 로그 레벨 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# 로거 설정
logger = get_logger(__name__, LOG_FILE, LOG_LEVEL)

def print_banner():
    """프로그램 시작 배너 출력"""
    banner = r"""
    ======================================================================
    네이버 의약품 정보 크롤러 v1.0
    ======================================================================
    """
    print(banner)

def validate_environment():
    """환경 검증"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        logger.error("Naver API 인증 정보가 설정되지 않았습니다!")
        print("오류: .env 파일에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 설정하세요.")
        sys.exit(1)

def parse_arguments():
    """
    명령줄 인자 파싱
    
    # 수정: 기존 parse_arguments 메서드에 DocID 관련 옵션 추가
    # 주요 변경: 새로운 크롤링 옵션 지원
    
    Returns:
        argparse.Namespace: 파싱된 명령줄 인자
    """
    parser = argparse.ArgumentParser(description='네이버 의약품 정보 크롤러')
    
    # 기존 모드 그룹 유지
    mode_group = parser.add_mutually_exclusive_group()
    
    # 기존 옵션들 (모두 유지)
    mode_group.add_argument('--all', action='store_true', help='모든 키워드로 검색')
    mode_group.add_argument('--keyword', help='특정 키워드로 검색')
    mode_group.add_argument('--url', help='특정 URL에서 정보 수집')
    mode_group.add_argument('--stats', action='store_true', help='데이터베이스 통계 출력')
    mode_group.add_argument('--export', action='store_true', help='수집된 데이터를 JSON으로 내보내기')
    mode_group.add_argument('--continue', dest='continue_last', action='store_true', help='마지막 체크포인트에서 계속')
    # DocID 관련 새로운 옵션 추가
    mode_group.add_argument(
        '--docid-range', 
        type=str, 
        help='시작,종료 DocID 범위 지정 (예: 1000,2000)'
    )
    mode_group.add_argument(
        '--find-docid-range', 
        action='store_true', 
        help='자동으로 의약품사전 DocID 범위 찾기'
    )
    mode_group.add_argument(
        '--retry-failed', 
        action='store_true', 
        help='실패한 URL 재시도'
    )

    # 기존 및 새로운 옵션들
    parser.add_argument(
        '--max-pages', 
        type=int, 
        default=MAX_PAGES_PER_KEYWORD, 
        help='키워드당 최대 페이지 수'
    )
    parser.add_argument(
        '--checkpoint', 
        type=str, 
        help='특정 체크포인트 파일 사용'
    )
    parser.add_argument(
        '--output', 
        type=str, 
        help='내보내기 파일 경로'
    )
    parser.add_argument(
        '--limit', 
        type=int, 
        help='검색할 최대 키워드 수'
    )
    parser.add_argument(
        '--max-items', 
        type=int, 
        default=None, 
        help='최대 수집 항목 수 제한'
    )

    # 인자 파싱
    args = parser.parse_args()

    # 기본값 설정 (기존 로직 유지)
    if not any([
        args.all, args.keyword, args.url, args.stats, 
        args.export, args.continue_last, args.retry_failed,
        args.docid_range, args.find_docid_range
    ]):
        # 기본적으로 DocID 범위 자동 탐색으로 변경
        args.find_docid_range = True

    return args

def init_components():
    """컴포넌트 초기화"""
    # 데이터베이스 매니저 초기화
    db_manager = DatabaseManager()
    
    # API 클라이언트 초기화
    api_client = NaverAPIClient(db_manager)
    
    # 파서 초기화
    parser = MedicineParser()
    
    # 검색 관리자 초기화
    search_manager = SearchManager(api_client, db_manager, parser)
    
    return db_manager, api_client, parser, search_manager

def search_all_keywords(search_manager, max_pages, limit=None):
    """
    의약품 데이터 수집
    
    Args:
        search_manager: SearchManager 인스턴스
        max_pages: 검색 페이지 수
        limit: 무시됨 (호환성을 위해 유지)
    """
    # 의약품 검색 페이지에서 URL 링크 수집
    urls = search_manager.fetch_medicine_list_from_search(start_page=1, max_pages=100)
    
    # 수집된 URL로 의약품 데이터 추출
    stats = search_manager.fetch_medicine_data_from_urls(urls)
    
    # 결과 출력
    print("\n검색 완료:")
    print(f"총 발견 링크: {len(urls)}개")
    print(f"총 수집 항목: {stats['saved_items']}개")
    print(f"소요 시간: {stats['duration_seconds']:.1f}초\n")
    
    return stats

def search_single_keyword(search_manager, keyword, max_pages):
    """단일 키워드로 검색"""
    log_section(logger, f"키워드 '{keyword}'로 검색 시작")
    
    # 검색 실행
    start_time = datetime.now()
    fetched, calls = search_manager.fetch_keyword_data(keyword, max_pages)
    duration = (datetime.now() - start_time).total_seconds()
    
    # 결과 출력
    print("\n검색 완료:")
    print(f"수집 항목: {fetched}개")
    print(f"API 호출: {calls}회")
    print(f"소요 시간: {duration:.1f}초\n")
    
    return {'fetched': fetched, 'calls': calls, 'duration': duration}

def process_single_url(search_manager, url):
    """단일 URL 처리"""
    log_section(logger, f"URL '{url}' 처리 시작")
    
    # URL 처리
    start_time = datetime.now()
    result = search_manager.fetch_single_url(url)
    duration = (datetime.now() - start_time).total_seconds()
    
    # 결과 출력
    print("\n처리 완료:")
    if result['success']:
        print(f"의약품명: {result['korean_name']}")
        print(f"의약품 ID: {result['medicine_id']}")
        print(f"JSON 파일: {result['json_path']}")
    else:
        print(f"처리 실패: {result['reason']}")
    
    print(f"소요 시간: {duration:.1f}초\n")
    
    return result

def continue_from_checkpoint(search_manager, checkpoint_file=None):
    """체크포인트에서 계속"""
    log_section(logger, "체크포인트에서 계속")
    
    # 체크포인트 로드
    checkpoint = load_checkpoint(checkpoint_file)
    
    if not checkpoint:
        logger.warning("사용 가능한 체크포인트가 없습니다.")
        print("오류: 사용 가능한 체크포인트가 없습니다.")
        return None
    
    logger.info(f"체크포인트 로드: {checkpoint.get('timestamp')}")
    
    # 키워드와 시작 위치 추출
    current_keyword = checkpoint.get('current_keyword')
    current_start = checkpoint.get('current_start', 1)
    
    if not current_keyword:
        logger.warning("체크포인트에 현재 키워드 정보가 없습니다.")
        print("오류: 체크포인트에 현재 키워드 정보가 없습니다.")
        return None
    
    # 나머지 키워드 추출
    all_keywords = generate_keywords_for_medicines()
    
    # 현재 키워드의 인덱스 찾기
    try:
        current_index = all_keywords.index(current_keyword)
    except ValueError:
        # 키워드가 목록에 없으면 추가
        current_index = 0
        all_keywords.insert(0, current_keyword)
    
    # 현재 키워드 이후의 키워드만 사용
    remaining_keywords = all_keywords[current_index:]
    
    logger.info(f"남은 키워드: {len(remaining_keywords)}개, 시작 위치: {current_keyword}")
    
    # 검색 실행
    stats = search_manager.fetch_all_keywords(remaining_keywords, MAX_PAGES_PER_KEYWORD)
    
    # 결과 출력
    print("\n검색 완료:")
    print(f"총 수집 항목: {stats['total_fetched']}개")
    print(f"총 API 호출: {stats['total_calls']}회")
    print(f"처리된 키워드: {stats['keywords_processed']}/{stats['keywords_total']}")
    print(f"소요 시간: {stats['duration_seconds']:.1f}초\n")
    
    return stats

def show_database_stats(db_manager):
    """데이터베이스 통계 출력"""
    log_section(logger, "데이터베이스 통계")
    
    # 의약품 수 조회
    medicines_count = db_manager.get_medicines_count()
    
    # 결과 출력
    print("\n데이터베이스 통계:")
    print(f"저장된 의약품 수: {medicines_count}개\n")
    
    return {'medicines_count': medicines_count}

def export_data(db_manager, output=None, format='json'):
    """
    데이터 내보내기
    
    Args:
        db_manager: 데이터베이스 관리자
        output: 출력 파일 경로 (None이면 자동 생성)
        format: 내보내기 형식 ('json', 'csv')
    
    Returns:
        dict: 내보내기 결과 정보
    """
    log_section(logger, "데이터 내보내기")
    
    # 의약품 수 조회
    medicines_count = db_manager.get_medicines_count()
    
    if medicines_count == 0:
        logger.warning("내보낼 데이터가 없습니다.")
        print("오류: 내보낼 데이터가 없습니다.")
        return None
    
    try:
        # 형식에 따른 내보내기
        if format.lower() == 'json':
            output_path = db_manager.export_to_json(output)
        elif format.lower() == 'csv':
            output_path = db_manager.export_to_csv(output)
        else:
            raise ValueError(f"지원하지 않는 형식: {format}")
        
        # 결과 출력
        print(f"\n데이터 내보내기 완료: {output_path}")
        print(f"의약품 수: {medicines_count}개\n")
        
        return {
            'output': output_path, 
            'count': medicines_count,
            'format': format
        }
    
    except Exception as e:
        logger.error(f"데이터 내보내기 오류: {e}")
        print(f"오류: 데이터 내보내기 실패 - {e}")
        return None

def import_data(db_manager, input_path):
    """
    데이터 가져오기
    
    Args:
        db_manager: 데이터베이스 관리자
        input_path: 가져올 파일 경로
    
    Returns:
        dict: 가져오기 결과 정보
    """
    log_section(logger, "데이터 가져오기")
    
    try:
        # 파일 확장자에 따른 가져오기 방식 선택
        file_ext = os.path.splitext(input_path)[1].lower()
        
        if file_ext == '.json':
            imported_count = db_manager.import_from_json(input_path)
        elif file_ext == '.csv':
            imported_count = db_manager.import_from_csv(input_path)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
        
        # 결과 출력
        print(f"\n데이터 가져오기 완료: {input_path}")
        print(f"추가된 의약품 수: {imported_count}개\n")
        
        return {
            'input': input_path, 
            'count': imported_count,
            'format': file_ext[1:]
        }
    
    except Exception as e:
        logger.error(f"데이터 가져오기 오류: {e}")
        print(f"오류: 데이터 가져오기 실패 - {e}")
        return None

def retry_failed_urls():
    """
    실패한 URL을 다시 시도합니다
    """
    log_section(logger, "실패한 URL 재시도")
    
    # 실패한 URL 파일 경로
    failed_urls_path = os.path.join(os.getcwd(), 'debug_html', 'failed_urls.json')
    
    # 파일이 없으면 중단
    if not os.path.exists(failed_urls_path):
        logger.info("실패한 URL 파일이 없습니다")
        return
    
    # 실패한 URL 목록 로드
    with open(failed_urls_path, 'r', encoding='utf-8') as f:
        failed_urls_data = json.load(f)
    
    # URL만 추출
    failed_urls = [item['url'] for item in failed_urls_data]
    
    if not failed_urls:
        logger.info("재시도할 URL이 없습니다")
        return
    
    logger.info(f"총 {len(failed_urls)}개의 실패한 URL을 재시도합니다")
    
    # 컴포넌트 초기화
    db_manager = DatabaseManager()
    api_client = NaverAPIClient(db_manager)
    parser = MedicineParser()
    search_manager = SearchManager(api_client, db_manager, parser)
    
    # 최대 재시도 횟수 증가
    stats = search_manager.fetch_medicine_data_from_urls(failed_urls, max_retries=5)
    
    # 결과 출력
    print("\n실패한 URL 재시도 완료:")
    print(f"처리된 URL: {stats['processed_urls']}/{len(failed_urls)}")
    print(f"저장된 항목: {stats['saved_items']}")
    print(f"여전히 실패한 URL: {stats['failed_urls_count']}")
    print(f"소요 시간: {stats['duration_seconds']:.1f}초\n")
    
    return stats

def main():
    """
    메인 함수
    
    # 수정: DocID 기반 크롤링 옵션 추가
    # 새로운 크롤링 전략 통합
    """
    try:
        # 시작 시간
        start_time = datetime.now()
        
        # 배너 출력
        print_banner()
        
        # 환경 검증
        validate_environment()
        
        # 인자 파싱
        args = parse_arguments()
        print(args)
        
        # 컴포넌트 초기화
        db_manager, api_client, parser, search_manager = init_components()
        
         # 크롤링 옵션에 따른 분기
        if args.docid_range:
            # 사용자 지정 DocID 범위로 크롤링
            try:
                start_docid, end_docid = map(int, args.docid_range.split(','))
                logger.info(f"사용자 지정 DocID 범위: {start_docid} ~ {end_docid}")
                stats = search_manager.fetch_medicine_docid_range(
                    start_docid, 
                    end_docid, 
                    max_items=args.max_items
                )
            except ValueError:
                logger.error("잘못된 DocID 범위 형식. 'start,end' 형태로 입력하세요.")
                return 1
        
        elif args.find_docid_range or not any([
            args.all, args.keyword, args.url, args.stats, 
            args.export, args.continue_last, args.retry_failed
        ]):
            # 자동으로 DocID 범위 찾기 (기본 동작)
            start_docid, end_docid = search_manager.find_medicine_docid_range()
            
            if start_docid and end_docid:
                stats = search_manager.fetch_medicine_docid_range(
                    start_docid, 
                    end_docid, 
                    max_items=args.max_items
                )
            else:
                logger.error("DocID 범위를 찾을 수 없습니다.")
                return 1
        
        elif args.find_docid_range:
            # 자동으로 DocID 범위 찾기
            start_docid, end_docid = search_manager.find_medicine_docid_range()
            
            if start_docid and end_docid:
                stats = search_manager.fetch_medicine_docid_range(
                    start_docid, 
                    end_docid, 
                    max_items=args.max_items
                )
            else:
                logger.error("DocID 범위를 찾을 수 없습니다.")
                return 1
        
        elif args.retry_failed:
            # 실패한 URL 재시도
            retry_failed_urls()
        
        elif args.all:
            # 모든 키워드로 검색
            search_all_keywords(search_manager, args.max_pages, args.limit)
        
        elif args.keyword:
            # 단일 키워드로 검색
            search_single_keyword(search_manager, args.keyword, args.max_pages)
        
        elif args.url:
            # 단일 URL 처리
            process_single_url(search_manager, args.url)
        
        elif args.stats:
            # 데이터베이스 통계 출력
            show_database_stats(db_manager)
        
        elif args.export:
            # 데이터 내보내기
            export_data(db_manager, args.output)
        
        elif args.continue_last:
            # 체크포인트에서 계속
            continue_from_checkpoint(search_manager, args.checkpoint)
        
        # 종료 시간 및 소요 시간 계산
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 로깅
        log_section(logger, "프로그램 종료")
        logger.info(f"시작 시간: {start_time}")
        logger.info(f"종료 시간: {end_time}")
        logger.info(f"소요 시간: {duration}")
        
        print(f"\n프로그램 종료. 총 소요 시간: {duration}\n")
        return 0
        
    except KeyboardInterrupt:
        print("\n\n프로그램이 사용자에 의해 중단되었습니다 (Ctrl+C)")
        logger.warning("사용자에 의해 프로그램이 중단되었습니다")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n\n오류 발생: {e}")
        log_exception(logger, e, "프로그램 실행 중 오류 발생")
        return 1

# main 함수 실행 부분
if __name__ == "__main__":
    sys.exit(main())