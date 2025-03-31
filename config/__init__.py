# crawler/__init__.py
"""
크롤러 패키지 초기화
"""
from .api_client import NaverAPIClient
from .parser import MedicineParser
from .search_manager import SearchManager

# db/__init__.py
"""
데이터베이스 패키지 초기화
"""
from .db_manager import DatabaseManager
from .models import Medicine, ApiCall

# utils/__init__.py
"""
유틸리티 패키지 초기화
"""
from .logger import get_logger, log_section, log_exception
from .helpers import (
    retry, clean_text, clean_html, extract_numeric, 
    generate_safe_filename, generate_data_hash,
    save_json, load_json, merge_dicts, is_valid_url,
    create_keyword_list, generate_keywords_for_medicines
)
from .file_handler import (
    download_image, save_medicine_json, save_checkpoint, 
    load_checkpoint, ensure_dir
)

# config/__init__.py
"""
설정 패키지 초기화
"""
from .settings import (
    ROOT_DIR, DATA_DIR, IMAGES_DIR, JSON_DIR, CHECKPOINT_DIR,
    NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, DB_TYPE, DATABASE_URL,
    MAX_RETRIES, REQUEST_DELAY, MAX_PAGES_PER_KEYWORD, DAILY_API_LIMIT,
    CHECKPOINT_INTERVAL, LOG_LEVEL, LOG_FILE, LOG_LEVEL_MAP,
    MEDICINE_PATTERNS, SEARCH_DEFAULTS, MEDICINE_SECTIONS, MEDICINE_PROFILE_ITEMS,
    MEDICINE_SCHEMA
)