"""
로깅 설정 및 유틸리티
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
from datetime import datetime

# 로그 색상 지정 (터미널 컬러 지원)
class ColorFormatter(logging.Formatter):
    """
    컬러 지원 로그 포매터
    """
    # 색상 코드
    COLORS = {
        'DEBUG': '\033[94m',  # 파란색
        'INFO': '\033[92m',   # 초록색
        'WARNING': '\033[93m', # 노란색
        'ERROR': '\033[91m',  # 빨간색
        'CRITICAL': '\033[1;91m',  # 굵은 빨간색
        'RESET': '\033[0m'    # 리셋
    }

    def format(self, record):
        log_message = super().format(record)
        if record.levelname in self.COLORS:
            log_message = f"{self.COLORS[record.levelname]}{log_message}{self.COLORS['RESET']}"
        return log_message

def setup_logger(name, log_file=None, log_level=logging.INFO):
    """
    로거 설정 함수
    
    Args:
        name: 로거 이름
        log_file: 로그 파일 경로 (None이면 콘솔에만 출력)
        log_level: 로그 레벨
        
    Returns:
        logging.Logger: 설정된 로거 객체
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # 이미 핸들러가 있으면 제거 (중복 방지)
    if logger.handlers:
        logger.handlers = []
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # 컬러 포매터 적용
    console_formatter = ColorFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 설정 (로그 파일이 지정된 경우)
    if log_file:
        # 로그 파일 디렉토리 생성
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # 로테이팅 파일 핸들러 (최대 10MB, 백업 5개)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        
        # 파일용 포매터 설정
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name=None, log_file=None, log_level=None):
    """
    설정 파일을 참조하여 로거 생성
    
    Args:
        name: 로거 이름 (기본값: 'naver_medicine_crawler')
        log_file: 로그 파일 경로 (기본값: 설정 파일 값)
        log_level: 로그 레벨 (기본값: 설정 파일 값)
        
    Returns:
        logging.Logger: 로거 객체
    """
    from config.settings import LOG_LEVEL_MAP, LOG_LEVEL, LOG_FILE
    
    if name is None:
        name = 'naver_medicine_crawler'
    
    if log_file is None:
        log_file = LOG_FILE
    
    if log_level is None:
        log_level = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO)
    
    return setup_logger(name, log_file, log_level)

def log_section(logger, title, char='=', length=80):
    """
    구분선과 함께 섹션 제목 로깅
    
    Args:
        logger: 로거 객체
        title: 섹션 제목
        char: 구분선 문자
        length: 구분선 길이
    """
    logger.info(char * length)
    logger.info(title.center(length))
    logger.info(char * length)

def log_exception(logger, exception, message=None):
    """
    예외 상세 정보 로깅
    
    Args:
        logger: 로거 객체 
        exception: 예외 객체
        message: 추가 메시지
    """
    import traceback
    
    if message:
        logger.error(message)
    
    logger.error(f"예외 타입: {type(exception).__name__}")
    logger.error(f"예외 메시지: {str(exception)}")
    
    # 스택 트레이스 로깅
    tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
    logger.error("상세 스택 트레이스:")
    for line in tb_lines:
        logger.error(line.rstrip())