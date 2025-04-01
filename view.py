"""
의약품 데이터 검색 및 출력을 위한 뷰 모듈
"""
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from crawler.api_client import NaverAPIClient
from crawler.parser import MedicineParser
from crawler.search_manager import SearchManager
from db.db_manager import DatabaseManager
from utils.logger import get_logger

# 로거 설정
logger = get_logger(__name__)

def view_extracted_links(max_pages=10):
    """
    추출된 의약품 링크 출력
    
    Args:
        max_pages: 최대 검색 페이지 수
    """
    # 컴포넌트 초기화
    db_manager = DatabaseManager()
    api_client = NaverAPIClient(db_manager)
    parser = MedicineParser()
    search_manager = SearchManager(api_client, db_manager, parser)
    
    # 링크 추출
    urls = search_manager.fetch_medicine_list_from_search(start_page=1, max_pages=max_pages)
    
    # 링크 출력
    print("\n=== 추출된 의약품 링크 ===")
    print(f"총 {len(urls)}개의 링크 추출됨\n")
    
    for i, url in enumerate(urls, 1):
        print(f"{i}. {url}")
    
    return urls

def view_link_details(urls):
    """
    추출된 링크의 상세 정보 출력
    
    Args:
        urls: 의약품 페이지 URL 리스트
    """
    # 컴포넌트 초기화
    db_manager = DatabaseManager()
    api_client = NaverAPIClient(db_manager)
    parser = MedicineParser()
    search_manager = SearchManager(api_client, db_manager, parser)
    
    print("\n=== 링크별 상세 정보 ===")
    
    # 유효한 URL만 필터링
    valid_urls = [url for url in urls if url.startswith('https://terms.naver.com')]
    
    print(f"유효한 URL 수: {len(valid_urls)}")
    
    for i, url in enumerate(valid_urls, 1):
        print(f"\n{i}. URL: {url}")
        
        try:
            # 데이터 추출
            medicine_data = search_manager.process_medicine_data(url)
            
            if medicine_data:
                # 추출된 데이터 출력
                for key, value in medicine_data.items():
                    print(f"  {key}: {value}")
            else:
                print("  데이터 추출 실패")
        
        except Exception as e:
            print(f"  오류 발생: {e}")

def main():
    """
    메인 실행 함수
    """
    try:
        # 링크 추출
        extracted_urls = view_extracted_links()
        
        # 상세 정보 확인 여부 선택
        view_details = input("\n추출된 링크의 상세 정보를 확인하시겠습니까? (y/n): ").lower()
        
        if view_details == 'y':
            view_link_details(extracted_urls)
    
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")

if __name__ == "__main__":
    main()