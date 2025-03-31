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
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(description='네이버 의약품 정보 크롤러')
    
    # 기본 작동 모드
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--all', action='store_true', help='모든 키워드로 검색')
    mode_group.add_argument('--keyword', help='특정 키워드로 검색')
    mode_group.add_argument('--url', help='특정 URL에서 정보 수집')
    mode_group.add_argument('--stats', action='store_true', help='데이터베이스 통계 출력')
    mode_group.add_argument('--export', action='store_true', help='수집된 데이터를 JSON으로 내보내기')
    mode_group.add_argument('--continue', dest='continue_last', action='store_true', help='마지막 체크포인트에서 계속')
    
    # 옵션
    parser.add_argument('--max-pages', type=int, default=MAX_PAGES_PER_KEYWORD, help='키워드당 최대 페이지 수')
    parser.add_argument('--checkpoint', type=str, help='특정 체크포인트 파일 사용')
    parser.add_argument('--output', type=str, help='내보내기 파일 경로')
    parser.add_argument('--limit', type=int, help='검색할 최대 키워드 수')
    
    # 파싱
    args = parser.parse_args()
    
    # 기본값 설정
    if not any([args.all, args.keyword, args.url, args.stats, args.export, args.continue_last]):
        args.all = True  # 기본적으로 모든 키워드 검색
    
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
    """모든 키워드로 검색"""
    log_section(logger, "모든 키워드로 검색 시작")
    
    # 키워드 생성
    keywords = generate_keywords_for_medicines()
    
    if limit and limit > 0:
        keywords = keywords[:limit]
    
    logger.info(f"생성된 키워드: {len(keywords)}개")
    
    # 검색 실행
    stats = search_manager.fetch_all_keywords(keywords, max_pages)
    
    # 결과 출력
    print("\n검색 완료:")
    print(f"총 수집 항목: {stats['total_fetched']}개")
    print(f"총 API 호출: {stats['total_calls']}회")
    print(f"처리된 키워드: {stats['keywords_processed']}/{stats['keywords_total']}")
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

def export_data(db_manager, output=None):
    """데이터 내보내기"""
    log_section(logger, "데이터 내보내기")
    
    if not output:
        # 기본 출력 파일명
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"medicine_export_{timestamp}.json"
    
    # TODO: 실제 내보내기 구현
    print(f"\n데이터 내보내기 준비 중: {output}\n")
    
    # 의약품 수 조회
    medicines_count = db_manager.get_medicines_count()
    
    if medicines_count == 0:
        logger.warning("내보낼 데이터가 없습니다.")
        print("오류: 내보낼 데이터가 없습니다.")
        return None
    
    # TODO: 실제 내보내기 기능 구현 필요
    # 지금은 더미 파일 생성
    with open(output, 'w', encoding='utf-8') as f:
        f.write(json.dumps({"count": medicines_count, "message": "내보내기 기능 준비 중"}, ensure_ascii=False, indent=2))
    
    print(f"내보내기 완료: {output}")
    print(f"의약품 수: {medicines_count}개\n")
    
    return {'output': output, 'count': medicines_count}

def main():
    """메인 함수"""
    try:
        # 시작 시간
        start_time = datetime.now()
        
        # 배너 출력
        print_banner()
        
        # 환경 검증
        validate_environment()
        
        # 인자 파싱
        args = parse_arguments()
        
        # 컴포넌트 초기화
        db_manager, api_client, parser, search_manager = init_components()
        
        # 명령에 따라 실행
        if args.all:
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
        
        log_section(logger, "프로그램 종료")
        logger.info(f"시작 시간: {start_time}")
        logger.info(f"종료 시간: {end_time}")
        logger.info(f"소요 시간: {duration}")
        
        print(f"\n프로그램 종료. 총 소요 시간: {duration}\n")
        return 0
        
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 프로그램이 중단되었습니다.")
        logger.warning("사용자에 의해 프로그램이 중단되었습니다.")
        return 1
        
    except Exception as e:
        print(f"\n\n오류 발생: {e}")
        log_exception(logger, e, "프로그램 실행 중 오류 발생")
        return 1

if __name__ == "__main__":
    sys.exit(main())