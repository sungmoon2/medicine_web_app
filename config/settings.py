"""
환경 설정 관리 모듈
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging

# 프로젝트 루트 디렉토리 설정
ROOT_DIR = Path(__file__).parent.parent.absolute()

# .env 파일 로드
env_path = ROOT_DIR / '.env'
load_dotenv(env_path)

# 기본 디렉토리 설정
DATA_DIR = ROOT_DIR / 'data'
IMAGES_DIR = DATA_DIR / 'images'
JSON_DIR = DATA_DIR / 'json'
CHECKPOINT_DIR = ROOT_DIR / 'checkpoints'

# 디렉토리가 없으면 생성
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

# Naver API 설정
NAVER_CLIENT_ID = os.getenv('NAVER_CLIENT_ID')
NAVER_CLIENT_SECRET = os.getenv('NAVER_CLIENT_SECRET')

# 인증 정보 확인
if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
    print("오류: 네이버 API 인증 정보가 설정되지 않았습니다.")
    print("'.env' 파일을 생성하고 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 설정하세요.")
    sys.exit(1)

# 데이터베이스 설정
DB_TYPE = os.getenv('DB_TYPE', 'sqlite')
DB_PATH = os.getenv('DB_PATH', 'data/medicines.db')

if DB_TYPE.lower() == 'mysql':
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'medicine_db')
    
    # MySQL 연결 문자열
    DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
else:
    # SQLite 연결 문자열 (절대 경로 사용)
    DB_FULL_PATH = ROOT_DIR / DB_PATH
    DATABASE_URL = f"sqlite:///{DB_FULL_PATH}"

# 크롤링 설정
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', 0.5))
MAX_PAGES_PER_KEYWORD = int(os.getenv('MAX_PAGES_PER_KEYWORD', 10))
DAILY_API_LIMIT = int(os.getenv('DAILY_API_LIMIT', 25000))

# 체크포인트 설정
CHECKPOINT_INTERVAL = int(os.getenv('CHECKPOINT_INTERVAL', 100))

# 로깅 설정
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'naver_medicine_crawler.log')

# 로그 레벨 매핑
LOG_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# 의약품 식별 패턴 - HTML 파싱에 사용
MEDICINE_PATTERNS = {
    'cite_class': 'cite',
    'medicine_keyword': '의약품사전',
    'title_class': 'headword',
    'english_name_class': 'word_txt',
    'profile_class': 'tmp_profile',
    'image_box_class': 'img_box',
    'content_agenda_class': 'tmp_agenda',
    'content_section_id_prefix': 'TABLE_OF_CONTENT',
    'content_text_class': 'txt'
}

# API 검색 기본 설정
SEARCH_DEFAULTS = {
    'display': 100,  # 한 페이지당 결과 수
    'start': 1,      # 시작 인덱스
    'sort': 'sim'    # 정렬 방식 (sim: 정확도, date: 날짜)
}

# 의약품 정보 섹션 매핑
MEDICINE_SECTIONS = {
    '성분정보': 'components',
    '효능효과': 'efficacy',
    '주의사항': 'precautions',
    '용법용량': 'dosage',
    '저장방법': 'storage',
    '사용기간': 'period'
}

# 의약품 정보 프로필 항목 매핑
MEDICINE_PROFILE_ITEMS = {
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

# 의약품 데이터베이스 스키마 정의
MEDICINE_SCHEMA = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'korean_name': 'TEXT NOT NULL',
    'english_name': 'TEXT',
    'category': 'TEXT',
    'type': 'TEXT',
    'company': 'TEXT',
    'appearance': 'TEXT',
    'insurance_code': 'TEXT',
    'shape': 'TEXT',
    'color': 'TEXT',
    'size': 'TEXT',
    'identification': 'TEXT',
    'components': 'TEXT',
    'efficacy': 'TEXT',
    'precautions': 'TEXT',
    'dosage': 'TEXT',
    'storage': 'TEXT',
    'period': 'TEXT',
    'image_url': 'TEXT',
    'image_path': 'TEXT',
    'url': 'TEXT UNIQUE',
    'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    'data_hash': 'TEXT'
}
MEDICINE_PATTERNS.update({
    'size_ct_class': ['size_ct_v2'],
    'profile_wrap_class': ['profile_wrap'],
    'section_title_class': ['section'],
    'content_selectors': [
        'div.content',
        'p.txt',
        'div.txt'
    ]
})