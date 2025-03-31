"""
파일 처리 유틸리티
"""
import os
import json
import shutil
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from config.settings import IMAGES_DIR, JSON_DIR, CHECKPOINT_DIR
from utils.logger import get_logger
from utils.helpers import generate_safe_filename

# 로거 설정
logger = get_logger(__name__)

def ensure_dir(directory):
    """
    디렉토리가 없으면 생성
    
    Args:
        directory: 생성할 디렉토리 경로
        
    Returns:
        bool: 성공 여부
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"디렉토리 생성 실패: {directory}, 오류: {e}")
        return False

def save_checkpoint(data, filename=None):
    """
    체크포인트 저장
    
    Args:
        data: 저장할 데이터
        filename: 파일명 (None이면 타임스탬프 사용)
        
    Returns:
        str: 저장된 파일 경로 또는 None (실패 시)
    """
    try:
        # 디렉토리 확인
        ensure_dir(CHECKPOINT_DIR)
        
        # 파일명 생성
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"checkpoint_{timestamp}.json"
        
        file_path = os.path.join(CHECKPOINT_DIR, filename)
        
        # JSON 형식으로 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"체크포인트 저장 완료: {file_path}")
        return file_path
    
    except Exception as e:
        logger.error(f"체크포인트 저장 실패: {e}")
        return None

def load_checkpoint(filename=None):
    """
    체크포인트 로드
    
    Args:
        filename: 로드할 파일명 (None이면 가장 최근 파일)
        
    Returns:
        dict: 로드된 데이터 또는 None (실패 시)
    """
    try:
        if not os.path.exists(CHECKPOINT_DIR):
            logger.warning(f"체크포인트 디렉토리가 없음: {CHECKPOINT_DIR}")
            return None
        
        # 파일명이 지정되지 않은 경우 최신 파일 찾기
        if filename is None:
            checkpoint_files = [f for f in os.listdir(CHECKPOINT_DIR) if f.endswith('.json')]
            if not checkpoint_files:
                logger.warning("체크포인트 파일이 없음")
                return None
            
            # 수정 시간 기준 최신 파일
            checkpoint_files.sort(key=lambda x: os.path.getmtime(os.path.join(CHECKPOINT_DIR, x)), reverse=True)
            filename = checkpoint_files[0]
        
        file_path = os.path.join(CHECKPOINT_DIR, filename)
        
        # 파일 존재 확인
        if not os.path.exists(file_path):
            logger.warning(f"체크포인트 파일이 없음: {file_path}")
            return None
        
        # JSON 파일 로드
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        logger.info(f"체크포인트 로드 완료: {file_path}")
        return data
    
    except Exception as e:
        logger.error(f"체크포인트 로드 실패: {e}")
        return None

def save_medicine_json(medicine_data, medicine_id=None):
    """
    의약품 정보를 JSON 파일로 저장
    
    Args:
        medicine_data: 저장할 의약품 데이터
        medicine_id: 의약품 ID (None이면 생성)
        
    Returns:
        str: 저장된 파일 경로 또는 None (실패 시)
    """
    try:
        # 디렉토리 확인
        ensure_dir(JSON_DIR)
        
        # 파일명 생성
        if medicine_id is None:
            if 'id' in medicine_data:
                medicine_id = medicine_data['id']
            else:
                medicine_id = hashlib.md5(str(medicine_data).encode()).hexdigest()[:8]
        
        # 파일명에 의약품 이름 포함
        medicine_name = medicine_data.get('korean_name', '')
        if medicine_name:
            safe_name = generate_safe_filename(medicine_name, max_length=50)
            filename = f"{medicine_id}_{safe_name}.json"
        else:
            filename = f"{medicine_id}.json"
        
        file_path = os.path.join(JSON_DIR, filename)
        
        # JSON 형식으로 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(medicine_data, f, ensure_ascii=False, indent=2)
            
        logger.debug(f"의약품 정보 저장 완료: {file_path}")
        return file_path
    
    except Exception as e:
        logger.error(f"의약품 정보 저장 실패: {e}")
        return None

def download_image(image_url, medicine_name=None, timeout=10):
    """
    이미지 URL에서 이미지 다운로드
    
    Args:
        image_url: 이미지 URL
        medicine_name: 약품 이름 (파일명 생성용)
        timeout: 요청 타임아웃 (초)
        
    Returns:
        str: 로컬에 저장된 이미지 경로 또는 None (실패 시)
    """
    if not image_url:
        return None
    
    try:
        # 디렉토리 확인
        ensure_dir(IMAGES_DIR)
        
        # 파일명 생성
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
        
        if medicine_name:
            safe_name = generate_safe_filename(medicine_name, max_length=50)
            filename = f"{safe_name}_{url_hash}"
        else:
            filename = f"medicine_image_{url_hash}"
        
        # 파일 확장자 결정
        if '.' in image_url.split('?')[0].split('/')[-1]:
            ext = image_url.split('?')[0].split('/')[-1].split('.')[-1].lower()
            if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                filename = f"{filename}.{ext}"
            else:
                filename = f"{filename}.jpg"
        else:
            filename = f"{filename}.jpg"
        
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # 이미 다운로드된 파일이면 해당 경로 반환
        if os.path.exists(file_path):
            logger.debug(f"이미 다운로드된 이미지: {file_path}")
            return file_path
        
        # 이미지 다운로드
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(image_url, headers=headers, stream=True, timeout=timeout)
        response.raise_for_status()
        
        # 콘텐츠 타입 확인
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('image/'):
            logger.warning(f"이미지가 아닌 콘텐츠: {content_type}, URL: {image_url}")
            return None
        
        # 파일 저장
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"이미지 다운로드 완료: {file_path}")
        return file_path
    
    except Exception as e:
        logger.error(f"이미지 다운로드 실패: {image_url}, 오류: {e}")
        return None

def clear_directory(directory, pattern=None):
    """
    디렉토리 내용 삭제
    
    Args:
        directory: 삭제할 디렉토리 경로
        pattern: 파일 패턴 (None이면 모든 파일)
        
    Returns:
        int: 삭제된 파일 수
    """
    try:
        if not os.path.exists(directory):
            return 0
        
        count = 0
        for item in os.listdir(directory):
            if pattern and not item.endswith(pattern):
                continue
                
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
                count += 1
        
        logger.info(f"{directory} 디렉토리에서 {count}개 파일 삭제됨")
        return count
    
    except Exception as e:
        logger.error(f"디렉토리 삭제 실패: {directory}, 오류: {e}")
        return 0

def get_directory_size(directory):
    """
    디렉토리 크기 계산
    
    Args:
        directory: 계산할 디렉토리 경로
        
    Returns:
        int: 디렉토리 크기 (바이트)
    """
    total_size = 0
    with os.scandir(directory) as it:
        for entry in it:
            if entry.is_file():
                total_size += entry.stat().st_size
            elif entry.is_dir():
                total_size += get_directory_size(entry.path)
    return total_size

def list_files(directory, pattern=None, sort_by='name'):
    """
    디렉토리 내 파일 목록 조회
    
    Args:
        directory: 조회할 디렉토리 경로
        pattern: 파일 패턴 (None이면 모든 파일)
        sort_by: 정렬 기준 ('name', 'date', 'size')
        
    Returns:
        list: 파일 정보 목록 (이름, 크기, 수정일)
    """
    try:
        if not os.path.exists(directory):
            return []
        
        files = []
        for item in os.listdir(directory):
            if pattern and not item.endswith(pattern):
                continue
                
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                stat = os.stat(item_path)
                files.append({
                    'name': item,
                    'path': item_path,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime)
                })
        
        # 정렬
        if sort_by == 'name':
            files.sort(key=lambda x: x['name'])
        elif sort_by == 'date':
            files.sort(key=lambda x: x['modified'], reverse=True)
        elif sort_by == 'size':
            files.sort(key=lambda x: x['size'], reverse=True)
        
        return files
    
    except Exception as e:
        logger.error(f"파일 목록 조회 실패: {directory}, 오류: {e}")
        return []

def make_archive(source_dir, output_filename, format='zip'):
    """
    디렉토리를 압축 파일로 생성
    
    Args:
        source_dir: 압축할 디렉토리
        output_filename: 출력 파일명 (확장자 제외)
        format: 압축 형식 ('zip', 'tar', 'gztar', 'bztar', 'xztar')
        
    Returns:
        str: 생성된 압축 파일 경로 또는 None (실패 시)
    """
    try:
        if not os.path.exists(source_dir):
            logger.error(f"소스 디렉토리가 없음: {source_dir}")
            return None
        
        archive_path = shutil.make_archive(
            output_filename, format, source_dir
        )
        
        logger.info(f"압축 파일 생성 완료: {archive_path}")
        return archive_path
    
    except Exception as e:
        logger.error(f"압축 파일 생성 실패: {e}")
        return None