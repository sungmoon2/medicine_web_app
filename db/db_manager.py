"""
데이터베이스 관리 모듈
"""
import os
import sqlite3
import json
import pymysql
from datetime import datetime
from pathlib import Path
from config.settings import (
    DB_TYPE, DATABASE_URL, MEDICINE_SCHEMA, ROOT_DIR
)
from utils.helpers import generate_data_hash, merge_dicts
from utils.logger import get_logger

# 로거 설정
logger = get_logger(__name__)

class DatabaseManager:
    """
    데이터베이스 관리를 담당하는 클래스
    """
    def __init__(self, init_db=True):
        """
        데이터베이스 관리자 초기화
        
        Args:
            init_db: 데이터베이스 초기화 여부
        """
        self.db_type = DB_TYPE.lower()
        self.db_url = DATABASE_URL
        
        # DB 초기화
        if init_db:
            self.init_db()
    
    def init_db(self):
        """
        데이터베이스 초기화 및 테이블 생성
        """
        if self.db_type == 'sqlite':
            self._init_sqlite()
        elif self.db_type == 'mysql':
            self._init_mysql()
        else:
            raise ValueError(f"지원하지 않는 데이터베이스 유형: {self.db_type}")
    
    def _init_sqlite(self):
        """SQLite 데이터베이스 초기화"""
        try:
            # 데이터베이스 파일 경로 가져오기
            db_path = self.db_url.replace('sqlite:///', '')
            
            # 절대 경로 확인
            if not os.path.isabs(db_path):
                db_path = os.path.join(ROOT_DIR, db_path)
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            logger.info(f"SQLite 데이터베이스 초기화: {db_path}")
            
            # 연결 생성
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # medicines 테이블 생성
            fields = []
            for field, field_type in MEDICINE_SCHEMA.items():
                fields.append(f"{field} {field_type}")
            
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS medicines (
                {', '.join(fields)}
            )
            """
            cursor.execute(create_table_sql)
            
            # api_calls 테이블 생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # URL 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON medicines (url)')
            
            # 데이터 해시 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_hash ON medicines (data_hash)')
            
            # API 호출 날짜 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_calls_date ON api_calls (date)')
            
            conn.commit()
            conn.close()
            
            logger.info("SQLite 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"SQLite 데이터베이스 초기화 오류: {e}", exc_info=True)
            raise
    
    def _init_mysql(self):
        """MySQL/MariaDB 데이터베이스 초기화"""
        try:
            # 데이터베이스 URL에서 연결 정보 추출
            # mysql+pymysql://user:password@host:port/database
            parts = self.db_url.replace('mysql+pymysql://', '').split('@')
            user_pass = parts[0].split(':')
            host_db = parts[1].split('/')
            
            user = user_pass[0]
            password = user_pass[1] if len(user_pass) > 1 else ''
            
            host_port = host_db[0].split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 3306
            
            database = host_db[1] if len(host_db) > 1 else ''
            
            logger.info(f"MySQL 데이터베이스 초기화: {host}:{port}/{database}")
            
            # 연결 생성
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                charset='utf8mb4'
            )
            cursor = conn.cursor()
            
            # 데이터베이스 생성
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            # 데이터베이스 선택
            cursor.execute(f"USE {database}")
            
            # medicines 테이블 생성
            fields = []
            for field, field_type in MEDICINE_SCHEMA.items():
                # SQLite와 MySQL 타입 변환
                field_type = field_type.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'INT AUTO_INCREMENT PRIMARY KEY')
                field_type = field_type.replace('TEXT', 'LONGTEXT')
                field_type = field_type.replace('TIMESTAMP', 'DATETIME')
                
                fields.append(f"{field} {field_type}")
            
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS medicines (
                {', '.join(fields)}
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            cursor.execute(create_table_sql)
            
            # api_calls 테이블 생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_calls (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE,
                count INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # 인덱스 생성
            cursor.execute('CREATE INDEX idx_url ON medicines (url(255))')
            cursor.execute('CREATE INDEX idx_data_hash ON medicines (data_hash(32))')
            cursor.execute('CREATE INDEX idx_api_calls_date ON api_calls (date)')
            
            conn.commit()
            conn.close()
            
            logger.info("MySQL 데이터베이스 초기화 완료")
            
        except Exception as e:
            logger.error(f"MySQL 데이터베이스 초기화 오류: {e}", exc_info=True)
            raise
    
    def get_connection(self):
        """
        데이터베이스 연결 객체 반환
        
        Returns:
            connection: 데이터베이스 연결 객체
        """
        if self.db_type == 'sqlite':
            db_path = self.db_url.replace('sqlite:///', '')
            
            # 절대 경로 확인
            if not os.path.isabs(db_path):
                db_path = os.path.join(ROOT_DIR, db_path)
                
            return sqlite3.connect(db_path)
        
        elif self.db_type == 'mysql':
            parts = self.db_url.replace('mysql+pymysql://', '').split('@')
            user_pass = parts[0].split(':')
            host_db = parts[1].split('/')
            
            user = user_pass[0]
            password = user_pass[1] if len(user_pass) > 1 else ''
            
            host_port = host_db[0].split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 3306
            
            database = host_db[1] if len(host_db) > 1 else ''
            
            return pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset='utf8mb4'
            )
    
    def get_api_call_count(self, date):
        """
        특정 날짜의 API 호출 횟수 조회
        
        Args:
            date: 조회할 날짜 (YYYY-MM-DD)
            
        Returns:
            int: API 호출 횟수 또는 None (오류 발생 시)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT count FROM api_calls WHERE date = ? ORDER BY id DESC LIMIT 1", 
                (date,)
            )
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return result[0]
            else:
                # 오늘 첫 API 호출이면 레코드 생성
                self.update_api_call_count(date, 0)
                return 0
                
        except Exception as e:
            logger.error(f"API 호출 횟수 조회 오류: {e}", exc_info=True)
            return None
    
    def update_api_call_count(self, date, count):
        """
        API 호출 횟수 업데이트
        
        Args:
            date: 업데이트할 날짜 (YYYY-MM-DD)
            count: 새 호출 횟수
            
        Returns:
            bool: 성공 여부
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 기존 레코드 확인
            cursor.execute("SELECT count FROM api_calls WHERE date = ?", (date,))
            result = cursor.fetchone()
            
            if result:
                # 레코드 업데이트
                cursor.execute(
                    "UPDATE api_calls SET count = ? WHERE date = ?",
                    (count, date)
                )
            else:
                # 새 레코드 생성
                cursor.execute(
                    "INSERT INTO api_calls (date, count) VALUES (?, ?)",
                    (date, count)
                )
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"API 호출 횟수 업데이트 오류: {e}", exc_info=True)
            return False
    
    def is_url_exists(self, url):
        """
        URL이 이미 데이터베이스에 있는지 확인
        
        Args:
            url: 확인할 URL
            
        Returns:
            bool: 존재하면 True, 없으면 False
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM medicines WHERE url = ?", (url,))
            result = cursor.fetchone()
            
            conn.close()
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"URL 존재 여부 확인 오류: {e}", exc_info=True)
            return False
    
    def is_data_hash_exists(self, data_hash):
        """
        데이터 해시가 이미 데이터베이스에 있는지 확인
        
        Args:
            data_hash: 확인할 데이터 해시
            
        Returns:
            bool: 존재하면 True, 없으면 False
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM medicines WHERE data_hash = ?", (data_hash,))
            result = cursor.fetchone()
            
            conn.close()
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"데이터 해시 존재 여부 확인 오류: {e}", exc_info=True)
            return False
    
    def save_medicine(self, medicine_data):
        """
        의약품 정보를 데이터베이스에 저장
        
        Args:
            medicine_data: 저장할 의약품 데이터
            
        Returns:
            int: 생성된 의약품 ID 또는 None (실패 시)
        """
        try:
            # URL 중복 확인
            if self.is_url_exists(medicine_data['url']):
                # 기존 데이터 업데이트
                return self.update_medicine_by_url(medicine_data['url'], medicine_data)
            
            # 데이터 해시 생성 (없으면)
            if 'data_hash' not in medicine_data:
                medicine_data['data_hash'] = generate_data_hash(medicine_data)
            
            # 데이터 해시로 중복 확인
            if self.is_data_hash_exists(medicine_data['data_hash']):
                logger.info(f"동일한 데이터 해시가 존재함: {medicine_data['data_hash']}")
                return None
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 현재 시간 추가
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            medicine_data['created_at'] = now
            medicine_data['updated_at'] = now
            
            # 필드와 값 준비
            fields = []
            placeholders = []
            values = []
            
            for field in MEDICINE_SCHEMA.keys():
                if field != 'id':  # id는 자동 생성
                    if field in medicine_data:
                        fields.append(field)
                        placeholders.append('?')
                        values.append(medicine_data[field])
            
            # 삽입 쿼리 실행
            insert_sql = f"""
            INSERT INTO medicines ({', '.join(fields)}) 
            VALUES ({', '.join(placeholders)})
            """
            cursor.execute(insert_sql, values)
            
            # 삽입된 ID 가져오기
            if self.db_type == 'sqlite':
                medicine_id = cursor.lastrowid
            else:
                cursor.execute("SELECT LAST_INSERT_ID()")
                medicine_id = cursor.fetchone()[0]
            
            conn.commit()
            conn.close()
            
            logger.info(f"의약품 저장 완료 (ID: {medicine_id}): {medicine_data.get('korean_name', '')}")
            return medicine_id
            
        except Exception as e:
            logger.error(f"의약품 저장 오류: {e}", exc_info=True)
            return None
    
    def update_medicine_by_url(self, url, new_data):
        """
        URL로 의약품 정보 업데이트
        
        Args:
            url: 업데이트할 의약품 URL
            new_data: 새 데이터
            
        Returns:
            int: 업데이트된 의약품 ID 또는 None (실패 시)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 기존 데이터 조회
            cursor.execute("SELECT * FROM medicines WHERE url = ?", (url,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                logger.warning(f"업데이트할 의약품을 찾을 수 없음: {url}")
                return None
            
            # 결과를 딕셔너리로 변환
            columns = [desc[0] for desc in cursor.description]
            
            if self.db_type == 'sqlite':
                existing_data = {columns[i]: result[i] for i in range(len(columns))}
            else:
                # pymysql에서는 컬럼 이름과 값을 직접 매핑
                existing_data = {}
                for i, column in enumerate(columns):
                    existing_data[column] = result[i]
            
            # 기존 ID 가져오기
            medicine_id = existing_data['id']
            
            # 데이터 병합 (기존 데이터 + 새 데이터)
            merged_data = merge_dicts(existing_data, new_data)
            
            # 현재 시간으로 업데이트 시간 설정
            merged_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 데이터 해시 업데이트
            merged_data['data_hash'] = generate_data_hash(merged_data)
            
            # 업데이트할 필드 준비
            update_fields = []
            values = []
            
            for field in MEDICINE_SCHEMA.keys():
                if field != 'id' and field in merged_data:  # id는 업데이트 불가
                    update_fields.append(f"{field} = ?")
                    values.append(merged_data[field])
            
            # URL 조건 추가
            values.append(url)
            
            # 업데이트 쿼리 실행
            update_sql = f"""
            UPDATE medicines 
            SET {', '.join(update_fields)}
            WHERE url = ?
            """
            cursor.execute(update_sql, values)
            
            conn.commit()
            conn.close()
            
            logger.info(f"의약품 업데이트 완료 (ID: {medicine_id}): {merged_data.get('korean_name', '')}")
            return medicine_id
            
        except Exception as e:
            logger.error(f"의약품 업데이트 오류: {e}", exc_info=True)
            return None
    
    def get_medicine_by_id(self, medicine_id):
        """
        ID로 의약품 정보 조회
        
        Args:
            medicine_id: 조회할 의약품 ID
            
        Returns:
            dict: 의약품 정보 또는 None (실패 시)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM medicines WHERE id = ?", (medicine_id,))
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return None
            
            # 결과를 딕셔너리로 변환
            columns = [desc[0] for desc in cursor.description]
            
            if self.db_type == 'sqlite':
                medicine_data = {columns[i]: result[i] for i in range(len(columns))}
            else:
                # pymysql에서는 컬럼 이름과 값을 직접 매핑
                medicine_data = {}
                for i, column in enumerate(columns):
                    medicine_data[column] = result[i]
            
            conn.close()
            
            return medicine_data
            
        except Exception as e:
            logger.error(f"의약품 조회 오류: {e}", exc_info=True)
            return None
    
    def get_medicine_by_name(self, name, limit=10):
        """
        이름으로 의약품 검색
        
        Args:
            name: 검색할 의약품 이름
            limit: 최대 결과 수
            
        Returns:
            list: 의약품 정보 목록
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM medicines WHERE korean_name LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{name}%", limit)
            )
            results = cursor.fetchall()
            
            # 결과가 없으면 빈 목록 반환
            if not results:
                conn.close()
                return []
            
            # 결과를 딕셔너리 목록으로 변환
            columns = [desc[0] for desc in cursor.description]
            medicines = []
            
            for result in results:
                if self.db_type == 'sqlite':
                    medicine_data = {columns[i]: result[i] for i in range(len(columns))}
                else:
                    # pymysql에서는 컬럼 이름과 값을 직접 매핑
                    medicine_data = {}
                    for i, column in enumerate(columns):
                        medicine_data[column] = result[i]
                
                medicines.append(medicine_data)
            
            conn.close()
            
            return medicines
            
        except Exception as e:
            logger.error(f"의약품 이름 검색 오류: {e}", exc_info=True)
            return []
    
    def get_medicines_count(self):
        """
        저장된 의약품 수 조회
        
        Returns:
            int: 의약품 수 또는 0 (실패 시)
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM medicines")
            result = cursor.fetchone()
            
            conn.close()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"의약품 수 조회 오류: {e}", exc_info=True)
            return 0
    
    def export_to_csv(self, output_path=None):
        """
        의약품 데이터를 CSV로 내보내기
        
        Args:
            output_path: 출력 파일 경로 (None이면 자동 생성)
        
        Returns:
            str: 내보낸 파일 경로
        """
        import csv
        from datetime import datetime
        
        try:
            # 출력 경로 설정
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(JSON_DIR, f"medicines_export_{timestamp}.csv")
            
            # 데이터베이스 연결
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 모든 의약품 데이터 조회
            cursor.execute("SELECT * FROM medicines")
            columns = [desc[0] for desc in cursor.description]
            
            # CSV 파일 쓰기
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                csv_writer = csv.writer(csvfile)
                
                # 헤더 쓰기
                csv_writer.writerow(columns)
                
                # 데이터 쓰기
                for row in cursor.fetchall():
                    csv_writer.writerow(row)
            
            conn.close()
            
            logger.info(f"CSV 내보내기 완료: {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"CSV 내보내기 오류: {e}", exc_info=True)
            return None
    
    def export_to_json(self, output_path=None):
        """
        의약품 데이터를 JSON으로 내보내기
        
        Args:
            output_path: 출력 파일 경로 (None이면 자동 생성)
        
        Returns:
            str: 내보낸 파일 경로
        """
        import json
        from datetime import datetime
        
        try:
            # 출력 경로 설정
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(JSON_DIR, f"medicines_export_{timestamp}.json")
            
            # 데이터베이스 연결
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 모든 의약품 데이터 조회
            cursor.execute("SELECT * FROM medicines")
            columns = [desc[0] for desc in cursor.description]
            
            # 데이터를 딕셔너리 리스트로 변환
            medicines = []
            for row in cursor.fetchall():
                medicine = dict(zip(columns, row))
                medicines.append(medicine)
            
            conn.close()
            
            # JSON 파일로 저장
            with open(output_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(medicines, jsonfile, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON 내보내기 완료: {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"JSON 내보내기 오류: {e}", exc_info=True)
            return None
    
    def import_from_csv(self, csv_path):
        """
        CSV에서 의약품 데이터 가져오기
        
        Args:
            csv_path: 가져올 CSV 파일 경로
        
        Returns:
            int: 가져온 의약품 수
        """
        import csv
        
        try:
            # CSV 파일 읽기
            with open(csv_path, 'r', encoding='utf-8') as csvfile:
                csv_reader = csv.DictReader(csvfile)
                
                # 불러온 데이터 저장
                imported_count = 0
                for row in csv_reader:
                    # URL 중복 체크
                    if not self.is_url_exists(row['url']):
                        # 의약품 데이터 저장
                        result = self.save_medicine(row)
                        if result:
                            imported_count += 1
                
                logger.info(f"CSV 가져오기 완료: {imported_count}개 의약품 추가")
                return imported_count
        
        except Exception as e:
            logger.error(f"CSV 가져오기 오류: {e}", exc_info=True)
            return 0
    
    def import_from_json(self, json_path):
        """
        JSON에서 의약품 데이터 가져오기
        
        Args:
            json_path: 가져올 JSON 파일 경로
        
        Returns:
            int: 가져온 의약품 수
        """
        import json
        
        try:
            # JSON 파일 읽기
            with open(json_path, 'r', encoding='utf-8') as jsonfile:
                medicines = json.load(jsonfile)
                
                # 불러온 데이터 저장
                imported_count = 0
                for medicine in medicines:
                    # URL 중복 체크
                    if not self.is_url_exists(medicine['url']):
                        # 의약품 데이터 저장
                        result = self.save_medicine(medicine)
                        if result:
                            imported_count += 1
                
                logger.info(f"JSON 가져오기 완료: {imported_count}개 의약품 추가")
                return imported_count
        
        except Exception as e:
            logger.error(f"JSON 가져오기 오류: {e}", exc_info=True)
            return 0