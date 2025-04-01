"""
의약품 데이터 검색 및 출력을 위한 뷰 모듈
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from crawler.api_client import NaverAPIClient
from crawler.parser import MedicineParser
from crawler.search_manager import SearchManager
from db.db_manager import DatabaseManager
from utils.logger import get_logger
from config.settings import MEDICINE_PROFILE_ITEMS, MEDICINE_SECTIONS

# 로거 설정
logger = get_logger(__name__)

class MedicineDataAnalyzer:
    def __init__(self, max_pages=10):
        """
        의약품 데이터 분석기 초기화
        
        Args:
            max_pages: 최대 검색 페이지 수
        """
        # 컴포넌트 초기화
        self.db_manager = DatabaseManager()
        self.api_client = NaverAPIClient(self.db_manager)
        self.parser = MedicineParser()
        self.search_manager = SearchManager(self.api_client, self.db_manager, self.parser)
        
        # 데이터 저장 변수
        self.extracted_urls = []
        self.extracted_medicine_data = []
        self.extracted_columns = set()
        self.missing_columns = set(list(MEDICINE_PROFILE_ITEMS.values()) + list(MEDICINE_SECTIONS.values()))
        self.column_completeness = {}
        
        # 최대 페이지 수
        self.max_pages = max_pages
    
    def extract_medicine_links(self):
        """
        의약품 링크 추출
        """
        # 링크 추출
        self.extracted_urls = self.search_manager.fetch_medicine_list_from_search(
            start_page=1, 
            max_pages=self.max_pages
        )
        
        print("\n=== 추출된 의약품 링크 ===")
        print(f"총 {len(self.extracted_urls)}개의 링크 추출됨\n")
        
        return self.extracted_urls
    
    def process_medicine_data(self, max_items=None):
        """
        링크 기반 의약품 데이터 처리
        
        Args:
            max_items: 최대 처리할 항목 수
        """
        # 유효한 URL만 필터링
        valid_urls = [url for url in self.extracted_urls if url.startswith('https://terms.naver.com')]
        
        # 최대 처리 항목 수 제한
        if max_items:
            valid_urls = valid_urls[:max_items]
        
        # 결과 저장 디렉토리 생성
        result_dir = os.path.join(project_root, 'debug_data')
        os.makedirs(result_dir, exist_ok=True)
        
        # 결과 파일 경로
        result_file_path = os.path.join(result_dir, 'medicine_data_analysis.json')
        
        print("\n=== 의약품 데이터 추출 시작 ===")
        print(f"총 {len(valid_urls)}개 URL 처리 예정")
        
        # 데이터 처리
        for idx, url in enumerate(valid_urls, 1):
            try:
                print(f"\n{idx}/{len(valid_urls)} URL 처리 중: {url}")
                
                # 데이터 추출
                medicine_data = self.search_manager.process_medicine_data(url)
                
                if medicine_data:
                    # 데이터 검증
                    validation_result = self.parser.validate_medicine_data(medicine_data)
                    
                    # 추출된 컬럼 업데이트
                    current_columns = set(medicine_data.keys()) - {'url', 'data_hash', 'created_at', 'updated_at'}
                    self.extracted_columns.update(current_columns)
                    
                    # 누락된 컬럼 업데이트
                    self.missing_columns -= current_columns
                    
                    # 컬럼 완전성 계산
                    for col in current_columns:
                        if col not in self.column_completeness:
                            self.column_completeness[col] = {
                                'total_count': 0,
                                'non_empty_count': 0,
                                'samples': []
                            }
                        
                        self.column_completeness[col]['total_count'] += 1
                        
                        if medicine_data[col]:
                            self.column_completeness[col]['non_empty_count'] += 1
                            
                            # 고유한 샘플 최대 5개 저장
                            sample = str(medicine_data[col])[:100]
                            if sample not in self.column_completeness[col]['samples']:
                                if len(self.column_completeness[col]['samples']) < 5:
                                    self.column_completeness[col]['samples'].append(sample)
                    
                    # 데이터 저장
                    self.extracted_medicine_data.append({
                        'url': url,
                        'korean_name': medicine_data.get('korean_name', ''),
                        'is_valid': validation_result['is_valid'],
                        'data': medicine_data
                    })
                else:
                    print(f"  데이터 추출 실패: {url}")
            
            except Exception as e:
                print(f"URL 처리 중 오류: {url}, {e}")
        
        # 결과 JSON 파일로 저장
        with open(result_file_path, 'w', encoding='utf-8') as f:
            json.dump(self.extracted_medicine_data, f, ensure_ascii=False, indent=2)
        
        return self
    
    def print_analysis_results(self):
        """
        분석 결과 출력
        """
        print("\n=== 의약품 데이터 분석 결과 ===")
        
        # 1. 추출된 링크 수
        print(f"1. 추출된 링크 수: {len(self.extracted_urls)}")
        
        # 2. 추출된 의약품 데이터 수
        print(f"2. 추출된 의약품 데이터 수: {len(self.extracted_medicine_data)}")
        
        # 3. 추출된 데이터 컬럼들
        print("3. 추출된 데이터 컬럼들:")
        for col in sorted(self.extracted_columns):
            completeness = self.column_completeness.get(col, {})
            total = completeness.get('total_count', 0)
            non_empty = completeness.get('non_empty_count', 0)
            completion_rate = (non_empty / total * 100) if total > 0 else 0
            
            print(f"   - {col}: {non_empty}/{total} ({completion_rate:.2f}%)")
            # 샘플 값 출력
            if completeness.get('samples'):
                print("     샘플 값:")
                for sample in completeness['samples']:
                    print(f"     > {sample}")
        
        # 4. 누락된 데이터 컬럼
        print("\n4. 누락된 데이터 컬럼들:")
        for col in sorted(self.missing_columns):
            print(f"   - {col}")
        
        print("\n분석 결과 상세 정보는 다음 파일에서 확인 가능합니다:")
        print(f"  {os.path.join(project_root, 'debug_data', 'medicine_data_analysis.json')}")

def main():
    """
    메인 실행 함수
    """
    try:
        # 의약품 데이터 분석기 생성 및 실행
        analyzer = MedicineDataAnalyzer(max_pages=10)
        
        # 링크 추출
        analyzer.extract_medicine_links()
        
        # 데이터 처리 (최대 50개 항목으로 제한)
        analyzer.process_medicine_data(max_items=50)
        
        # 결과 분석 및 출력
        analyzer.print_analysis_results()
    
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")

if __name__ == "__main__":
    main()