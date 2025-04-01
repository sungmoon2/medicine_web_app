import sqlite3

# 데이터베이스 연결
conn = sqlite3.connect('data/medicines.db')
cursor = conn.cursor()

# 테이블 구조 확인
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("데이터베이스 테이블:")
for table in tables:
    print(f"- {table[0]}")

# medicines 테이블이 있는지 확인
if ('medicines',) in tables:
    # 행 개수 확인
    cursor.execute("SELECT COUNT(*) FROM medicines")
    count = cursor.fetchone()[0]
    print(f"\n의약품 데이터 수: {count}개")
    
    # 테이블 구조 확인
    cursor.execute("PRAGMA table_info(medicines)")
    columns = cursor.fetchall()
    print("\n테이블 구조:")
    for col in columns:
        print(f"- {col[1]} ({col[2]})")
    
    # 샘플 데이터 확인 (있는 경우)
    if count > 0:
        cursor.execute("SELECT id, korean_name, english_name, company, created_at FROM medicines LIMIT 5")
        rows = cursor.fetchall()
        print("\n최근 데이터:")
        for row in rows:
            print(f"ID: {row[0]}, 이름: {row[1]}, 영문명: {row[2]}, 제조사: {row[3]}, 생성일: {row[4]}")
else:
    print("\nmedicines 테이블이 존재하지 않습니다.")

conn.close()