"""
의약품 데이터 검색 및 출력을 위한 뷰 모듈
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import json
import argparse

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from db.db_manager import DatabaseManager
from utils.logger import get_logger

# 로거 설정
logger = get_logger(__name__)

class MedicineDataViewer:
    def __init__(self, db_manager=None):
        """
        의약품 데이터 뷰어 초기화
        
        Args:
            db_manager: DatabaseManager 인스턴스 (None이면 새로 생성)
        """
        self.db_manager = db_manager or DatabaseManager()
    
    def view_medicines(self, limit=10, offset=0, 
                       show_details=False, 
                       search_name=None):
        """
        의약품 목록 및 상세 정보 출력
        
        Args:
            limit: 최대 출력 항목 수
            offset: 건너뛸 항목 수
            show_details: 상세 정보 표시 여부
            search_name: 검색할 의약품 이름
        """
        # 의약품 조회 방식 선택
        if search_name:
            medicines = self.db_manager.get_medicine_by_name(search_name, limit)
        else:
            medicines = self.db_manager.get_all_medicines_with_details(limit, offset)
        
        if not medicines:
            print("조회된 의약품이 없습니다.")
            return
        
        print(f"\n{'=' * 100}")
        print(f"{'의약품 목록':^100}")
        print(f"{'=' * 100}")
        
        for medicine in medicines:
            # 기본 정보 출력
            print(f"\n[ID: {medicine.get('id', 'N/A')}]")
            print(f"한글명: {medicine.get('korean_name', 'N/A')}")
            print(f"영문명: {medicine.get('english_name', 'N/A')}")
            
            # 상세 정보 표시 옵션
            if show_details:
                # 상세 정보 출력을 위해 전체 데이터 조회
                full_medicine_data = self.db_manager.get_medicine_by_id(medicine['id'])
                
                if full_medicine_data:
                    print("\n상세 정보:")
                    detail_fields = [
                        ('category', '분류'),
                        ('type', '구분'),
                        ('company', '제조사'),
                        ('appearance', '성상'),
                        ('insurance_code', '보험코드'),
                        ('shape', '모양'),
                        ('color', '색깔'),
                        ('size', '크기'),
                        ('identification', '분할선/식별표기'),
                        ('components', '성분정보'),
                        ('efficacy', '효능효과'),
                        ('precautions', '주의사항'),
                        ('dosage', '용법용량'),
                        ('storage', '저장방법'),
                        ('period', '사용기간')
                    ]
                    
                    for key, label in detail_fields:
                        value = full_medicine_data.get(key, '')
                        if value:
                            print(f"- {label}: {value}")
                
                if full_medicine_data.get('image_url'):
                    print(f"- 이미지 URL: {full_medicine_data['image_url']}")
            
            print('-' * 100)
    
    def count_medicines(self):
        """
        저장된 의약품 총 수 출력
        """
        count = self.db_manager.get_medicines_count()
        print(f"\n저장된 의약품 총 수: {count}개")

def main():
    """
    메인 실행 함수
    """
    parser = argparse.ArgumentParser(description='의약품 데이터 뷰어')
    
    # 옵션 추가
    parser.add_argument(
        '--limit', 
        type=int, 
        default=10, 
        help='출력할 최대 의약품 수 (기본값: 10)'
    )
    parser.add_argument(
        '--offset', 
        type=int, 
        default=0, 
        help='건너뛸 의약품 수 (기본값: 0)'
    )
    parser.add_argument(
        '--details', 
        action='store_true', 
        help='상세 정보 표시'
    )
    parser.add_argument(
        '--search', 
        type=str, 
        help='의약품명 검색'
    )
    parser.add_argument(
        '--count', 
        action='store_true', 
        help='저장된 의약품 총 수 표시'
    )
    
    # 인자 파싱
    args = parser.parse_args()
    
    try:
        # 의약품 데이터 뷰어 생성
        viewer = MedicineDataViewer()
        
        # 카운트 옵션
        if args.count:
            viewer.count_medicines()
            return
        
        # 의약품 목록 출력
        viewer.view_medicines(
            limit=args.limit, 
            offset=args.offset, 
            show_details=args.details, 
            search_name=args.search
        )
    
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")

if __name__ == "__main__":
    main()