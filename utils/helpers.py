"""
다양한 헬퍼 함수 모음
"""
import os
import re
import json
import hashlib
import time
import functools
from datetime import datetime
from pathlib import Path

def retry(max_tries=3, delay_seconds=1, backoff_factor=2, exceptions=(Exception,)):
    """
    함수 재시도 데코레이터
    
    Args:
        max_tries: 최대 시도 횟수
        delay_seconds: 재시도 간 대기 시간 (초)
        backoff_factor: 대기 시간 증가 계수
        exceptions: 재시도할 예외 유형 튜플
    
    Returns:
        decorator: 재시도 데코레이터
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_tries, delay_seconds
            last_exception = None
            
            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    mtries -= 1
                    if mtries == 0:
                        break
                        
                    time.sleep(mdelay)
                    mdelay *= backoff_factor
            
            # 모든 재시도 실패 시 마지막 예외 발생
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

def clean_text(text):
    """
    텍스트 정리 (불필요한 공백, 줄바꿈 제거)
    
    Args:
        text: 정리할 텍스트
        
    Returns:
        str: 정리된 텍스트
    """
    if not text:
        return ""
    
    # 불필요한 공백 및 줄바꿈 제거
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def clean_html(html_text):
    """
    HTML 태그 제거 및 텍스트 정리
    
    Args:
        html_text: 정리할 HTML 텍스트
    
    Returns:
        str: 정리된 텍스트
    """
    if not html_text:
        return ""
    
    # HTML 태그 제거
    text = re.sub(r'<.*?>', '', html_text)
    
    # 불필요한 공백 제거
    text = clean_text(text)
    
    return text

def extract_numeric(text):
    """
    텍스트에서 숫자만 추출
    
    Args:
        text: 숫자를 포함한 텍스트
        
    Returns:
        str: 추출된 숫자 문자열
    """
    if not text:
        return ""
    
    # 숫자와 소수점만 추출
    numeric = re.findall(r'[\d\.]+', text)
    if numeric:
        return numeric[0]
    return ""

def generate_safe_filename(text, max_length=100):
    """
    안전한 파일명 생성
    
    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        
    Returns:
        str: 안전한 파일명
    """
    if not text:
        return datetime.now().strftime("%Y%m%d%H%M%S")
    
    # 파일명으로 사용할 수 없는 문자 제거
    safe_name = re.sub(r'[\\/*?:"<>|]', "", text)
    
    # 공백을 밑줄로 변경
    safe_name = re.sub(r'\s+', '_', safe_name)
    
    # 길이 제한
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length]
    
    return safe_name

def generate_data_hash(data_dict):
    """
    데이터 사전에서 해시값 생성
    
    Args:
        data_dict: 해시를 생성할 데이터 사전
    
    Returns:
        str: 데이터의 MD5 해시값
    """
    # 해시에서 제외할 필드
    exclude_fields = ['id', 'created_at', 'updated_at', 'data_hash']
    
    # 핵심 필드만 추출하여 정렬
    key_fields = sorted([
        f"{k}:{str(v)}" for k, v in data_dict.items() 
        if k not in exclude_fields and v
    ])
    
    # 정렬된 필드를 문자열로 연결하고 해시 생성
    data_str = '||'.join(key_fields)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

def save_json(data, filepath, ensure_dir=True):
    """
    데이터를 JSON 파일로 저장
    
    Args:
        data: 저장할 데이터
        filepath: 파일 경로
        ensure_dir: 디렉토리 생성 여부
        
    Returns:
        bool: 성공 여부
    """
    try:
        # 디렉토리 생성
        if ensure_dir:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def load_json(filepath, default=None):
    """
    JSON 파일에서 데이터 로드
    
    Args:
        filepath: 파일 경로
        default: 실패 시 반환할 기본값
        
    Returns:
        dict: 로드된 데이터 또는 기본값
    """
    if not os.path.exists(filepath):
        return default
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def format_file_size(size_bytes):
    """
    바이트 크기를 읽기 쉬운 형식으로 변환
    
    Args:
        size_bytes: 바이트 단위 크기
        
    Returns:
        str: 변환된 크기 문자열
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.2f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"

def merge_dicts(dict1, dict2, prefer_dict2=True):
    """
    두 딕셔너리 병합
    
    Args:
        dict1: 첫 번째 딕셔너리
        dict2: 두 번째 딕셔너리
        prefer_dict2: 충돌 시 dict2 값 우선 여부
        
    Returns:
        dict: 병합된 딕셔너리
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result:
            # 충돌 처리
            if prefer_dict2:
                # dict2 값 우선
                if value:  # 빈 값이 아닌 경우에만 업데이트
                    result[key] = value
            else:
                # 빈 값이 아닌 경우 dict1 값 유지
                if not result[key] and value:
                    result[key] = value
        else:
            # 새 키는 그대로 추가
            result[key] = value
    
    return result

def is_valid_url(url):
    """
    URL 유효성 검사
    
    Args:
        url: 검사할 URL
        
    Returns:
        bool: 유효한 URL이면 True
    """
    pattern = re.compile(
        r'^(?:http|https)://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(pattern.match(url))

def create_keyword_list(start_with_korean=True):
    """
    포괄적인 검색 키워드 생성
    
    Args:
        start_with_korean: 한글 초성부터 시작할지 여부
        
    Returns:
        list: 검색에 사용할 키워드 리스트
    """
    keywords = []
    
    # 한글 초성 (모든 한글 약품명 포괄)
    if start_with_korean:
        keywords.extend(["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"])
    
    # 영문 알파벳
    keywords.extend(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    
    # 숫자
    keywords.extend([str(i) for i in range(10)])
    
    # 의약품 일반 분류
    keywords.extend([
        "의약품", "약품", "전문의약품", "일반의약품", "희귀의약품"
    ])
    
    # 주요 제약사
    companies = [
        "동아제약", "유한양행", "녹십자", "한미약품", "종근당", 
        "대웅제약", "일동제약", "보령제약", "SK케미칼", "삼성바이오로직스",
        "셀트리온", "JW중외제약", "한독"
    ]
    keywords.extend(companies)
    
    # 약물 분류
    categories = [
        "소화제", "진통제", "해열제", "항생제", "항히스타민제",
        "고혈압약", "당뇨약", "콜레스테롤약", "수면제", "항우울제",
        "항암제", "갑상선약", "비타민", "철분제", "혈압약"
    ]
    keywords.extend(categories)
    
    return list(set(keywords))  # 중복 제거

def load_completed_keywords(file_path):
    """
    완료된 키워드 목록 로드
    
    Args:
        file_path: 완료된 키워드 파일 경로
        
    Returns:
        set: 완료된 키워드 세트
    """
    try:
        if not os.path.exists(file_path):
            return set()
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return {line.strip() for line in f if line.strip()}
    except Exception:
        return set()

def save_completed_keyword(keyword, file_path):
    """
    완료된 키워드 저장
    
    Args:
        keyword: 저장할 키워드
        file_path: 파일 경로
        
    Returns:
        bool: 성공 여부
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(keyword + '\n')
        return True
    except Exception:
        return False

def generate_keywords_for_medicines():
    keywords = []
    
    # 의약품 분류별로 의미 있는 키워드 사용
    keywords.extend(["감기약", "진통제", "소화제", "항생제", "비타민"])
    
    # 인기 약품 및 브랜드명
    popular_brands = [
        "타이레놀", "게보린", "판콜", "부루펜", "아스피린", "베아제", "백초시럽", "판피린",
        "액티피드", "판콜에이", "신신파스", "제일쿨파스", "캐롤", "텐텐", "이가탄", "센트룸",
        "아로나민", "삐콤씨", "컨디션", "박카스", "인사돌", "우루사", "훼스탈"
    ]
    keywords.extend(popular_brands)
    
    # 제약회사 이름
    companies = [
        "동아제약", "유한양행", "녹십자", "한미약품", "종근당", 
        "대웅제약", "일동제약", "보령제약", "SK케미칼", "삼성바이오로직스"
    ]
    keywords.extend(companies)
    
    # 중복 제거 후 반환
    return list(set(keywords))