#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
추출된 의약품 데이터 확인 스크립트
"""
import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from tabulate import tabulate  # pip install tabulate

# 프로젝트 루트 디렉토리 설정
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# 설정 가져오기
from config.settings import DATABASE_URL, JSON_DIR

def get_db_connection():
    """SQLite 데이터베이스 연결 객체 반환"""
    db_path = DATABASE_URL.replace('sqlite:///', '')
    if not os.path.isabs(db_path):
        db_path = os.path.join(project_root, db_path)
    
    if not os.path.exists(db_path):
        print(f"오류: 데이터베이스 파일이 존재하지 않습니다: {db_path}")
        sys.exit(1)
    
    return sqlite3.connect(db_path)

def view_medicine_count():
    """데이터베이스의 의약품 수 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM medicines")
    count = cursor.fetchone()[0]
    
    print(f"\n데이터베이스에 저장된 의약품 수: {count}개")
    
    # 최근 추가된 의약품 수 (오늘)
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM medicines WHERE DATE(created_at) = ?", (today,))
    today_count = cursor.fetchone()[0]
    
    print(f"오늘 추가된 의약품 수: {today_count}개")
    
    conn.close()

def view_recent_medicines(limit=10):
    """최근 추가된 의약품 목록 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT id, korean_name, english_name, company, category, created_at 
    FROM medicines 
    ORDER BY created_at DESC 
    LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    medicines = cursor.fetchall()
    
    if not medicines:
        print("\n최근 추가된 의약품이 없습니다.")
        conn.close()
        return
    
    # 테이블 형식으로 출력
    headers = ["ID", "한글명", "영문명", "제조사", "분류", "추가일시"]
    table_data = []
    
    for med in medicines:
        row = []
        for item in med:
            if item is None:
                row.append("")
            elif isinstance(item, str) and len(item) > 30:
                row.append(item[:27] + "...")
            else:
                row.append(item)
        table_data.append(row)
    
    print("\n최근 추가된 의약품:")
    print(tabulate(table_data, headers=headers, tablefmt="pretty"))
    
    conn.close()

def view_medicine_details(medicine_id=None, name=None):
    """의약품 상세 정보 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if medicine_id:
        cursor.execute("SELECT * FROM medicines WHERE id = ?", (medicine_id,))
        medicine = cursor.fetchone()
        
        if not medicine:
            print(f"\n오류: ID가 {medicine_id}인 의약품을 찾을 수 없습니다.")
            conn.close()
            return
    
    elif name:
        cursor.execute("SELECT * FROM medicines WHERE korean_name LIKE ? ORDER BY id DESC LIMIT 5", (f"%{name}%",))
        medicines = cursor.fetchall()
        
        if not medicines:
            print(f"\n오류: '{name}'을 포함하는 의약품을 찾을 수 없습니다.")
            conn.close()
            return
        
        if len(medicines) > 1:
            # 여러 결과가 있으면 선택하도록 함
            print(f"\n'{name}'을 포함하는 의약품 {len(medicines)}개:")
            
            for i, med in enumerate(medicines):
                columns = [desc[0] for desc in cursor.description]
                med_dict = dict(zip(columns, med))
                print(f"{i+1}. {med_dict['korean_name']} (ID: {med_dict['id']})")
            
            choice = input("\n상세 정보를 볼 의약품 번호를 입력하세요 (기본: 1): ")
            try:
                idx = int(choice) - 1 if choice else 0
                if idx < 0 or idx >= len(medicines):
                    print("잘못된 번호입니다. 첫 번째 항목을 보여줍니다.")
                    idx = 0
            except ValueError:
                print("숫자를 입력해야 합니다. 첫 번째 항목을 보여줍니다.")
                idx = 0
            
            medicine = medicines[idx]
        else:
            medicine = medicines[0]
    
    else:
        print("\n오류: 의약품 ID 또는 이름을 지정해야 합니다.")
        conn.close()
        return
    
    # 컬럼 이름 가져오기
    columns = [desc[0] for desc in cursor.description]
    med_dict = dict(zip(columns, medicine))
    
    print("\n의약품 상세 정보:")
    print("=" * 80)
    print(f"ID: {med_dict['id']}")
    print(f"한글명: {med_dict['korean_name']}")
    print(f"영문명: {med_dict['english_name'] or '없음'}")
    print(f"제조사: {med_dict['company'] or '없음'}")
    print(f"분류: {med_dict['category'] or '없음'}")
    print("-" * 80)
    
    # 긴 텍스트 필드 출력
    for field in ['components', 'efficacy', 'precautions', 'dosage', 'storage', 'period']:
        if med_dict[field]:
            print(f"\n{field.upper()}:")
            print(med_dict[field])
    
    print("-" * 80)
    print(f"이미지 URL: {med_dict['image_url'] or '없음'}")
    print(f"이미지 경로: {med_dict['image_path'] or '없음'}")
    print(f"URL: {med_dict['url']}")
    print(f"생성일시: {med_dict['created_at']}")
    print(f"수정일시: {med_dict['updated_at']}")
    print("=" * 80)
    
    conn.close()

def view_json_file(medicine_id=None, name=None):
    """JSON 파일로 저장된 의약품 정보 확인"""
    if not medicine_id and not name:
        print("\n오류: 의약품 ID 또는 이름을 지정해야 합니다.")
        return
    
    json_dir = Path(JSON_DIR)
    if not json_dir.exists():
        print(f"\n오류: JSON 디렉토리가 존재하지 않습니다: {json_dir}")
        return
    
    # ID 또는 이름으로 JSON 파일 찾기
    if medicine_id:
        json_files = list(json_dir.glob(f"{medicine_id}_*.json"))
        if not json_files:
            json_files = list(json_dir.glob(f"{medicine_id}.json"))
    else:
        json_files = []
        for file in json_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if name.lower() in data.get('korean_name', '').lower():
                        json_files.append(file)
            except Exception:
                continue
    
    if not json_files:
        print(f"\n오류: 해당하는 JSON 파일을 찾을 수 없습니다.")
        return
    
    # JSON 파일 내용 출력
    json_file = json_files[0]
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\nJSON 파일: {json_file.name}")
        print("=" * 80)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print("=" * 80)
    except Exception as e:
        print(f"\n오류: JSON 파일을 읽는 중 오류 발생: {e}")

def main():
    """메인 함수"""
    while True:
        print("\n의약품 데이터 확인 도구")
        print("=" * 80)
        print("1. 저장된 의약품 수 확인")
        print("2. 최근 추가된 의약품 목록 보기")
        print("3. 의약품 상세 정보 보기 (ID로 검색)")
        print("4. 의약품 상세 정보 보기 (이름으로 검색)")
        print("5. JSON 파일 내용 보기 (ID로 검색)")
        print("6. JSON 파일 내용 보기 (이름으로 검색)")
        print("0. 종료")
        print("=" * 80)
        
        choice = input("\n선택: ")
        
        if choice == '1':
            view_medicine_count()
        
        elif choice == '2':
            limit = input("표시할 의약품 수 (기본: 10): ")
            try:
                limit = int(limit) if limit else 10
            except ValueError:
                limit = 10
            view_recent_medicines(limit)
        
        elif choice == '3':
            medicine_id = input("의약품 ID: ")
            try:
                medicine_id = int(medicine_id)
                view_medicine_details(medicine_id=medicine_id)
            except ValueError:
                print("오류: 숫자를 입력해야 합니다.")
        
        elif choice == '4':
            name = input("의약품 이름: ")
            if name:
                view_medicine_details(name=name)
            else:
                print("오류: 이름을 입력해야 합니다.")
        
        elif choice == '5':
            medicine_id = input("의약품 ID: ")
            try:
                medicine_id = int(medicine_id)
                view_json_file(medicine_id=medicine_id)
            except ValueError:
                print("오류: 숫자를 입력해야 합니다.")
        
        elif choice == '6':
            name = input("의약품 이름: ")
            if name:
                view_json_file(name=name)
            else:
                print("오류: 이름을 입력해야 합니다.")
        
        elif choice == '0':
            print("\n프로그램을 종료합니다.")
            break
        
        else:
            print("\n오류: 올바른 메뉴를 선택하세요.")
        
        input("\n계속하려면 Enter 키를 누르세요...")

if __name__ == "__main__":
    main()