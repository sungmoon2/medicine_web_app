"""
HTML 파싱 모듈
"""
import re
import urllib.parse
from bs4 import BeautifulSoup
from config.settings import MEDICINE_PATTERNS, MEDICINE_SECTIONS, MEDICINE_PROFILE_ITEMS
from utils.helpers import clean_text, generate_data_hash
from utils.logger import get_logger

# 로거 설정
logger = get_logger(__name__)

class MedicineParser:
    """
    의약품 정보 파싱 담당 클래스
    """
    def __init__(self):
        """의약품 파서 초기화"""
        pass
    
    def is_medicine_dictionary(self, soup, url):
        """
        HTML이 의약품사전 페이지인지 확인
        
        Args:
            soup: BeautifulSoup 객체
            url: 페이지 URL
        
        Returns:
            bool: 의약품사전이면 True
        """
        # URL 패턴 확인
        if 'terms.naver.com/entry.naver' not in url:
            return False
        
        # cite 클래스에 '의약품사전' 키워드가 있는지 확인
        cite_tag = soup.find('p', class_=MEDICINE_PATTERNS['cite_class'])
        if cite_tag and MEDICINE_PATTERNS['medicine_keyword'] in cite_tag.text:
            return True
        
        # 추가 검증: 헤딩 클래스 확인
        if soup.find('h2', class_=MEDICINE_PATTERNS['title_class']):
            return True
        
        return False
    
    def parse_medicine_detail(self, soup, url):
        """
        약품 상세 페이지에서 정보 파싱
        
        Args:
            soup: Beaut