"""
HTML 파싱 모듈
"""
import re
import urllib.parse
from bs4 import BeautifulSoup
from config.settings import MEDICINE_PATTERNS, MEDICINE_SECTIONS, MEDICINE_PROFILE_ITEMS
from utils.helpers import clean_text, clean_html, generate_data_hash
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
    
    def _extract_profile_info(self, soup):
        """
        의약품 프로필 정보 추출
        
        Args:
            soup: BeautifulSoup 객체
        
        Returns:
            dict: 추출된 프로필 정보
        """
        profile_info = {}
        
        # 프로필 섹션 찾기
        profile_section = soup.find('div', class_=MEDICINE_PATTERNS['profile_class'])
        
        if profile_section:
            # 각 프로필 항목 처리
            for term, mapped_key in MEDICINE_PROFILE_ITEMS.items():
                term_tag = profile_section.find('dt', string=re.compile(term))
                if term_tag:
                    value_tag = term_tag.find_next_sibling('dd')
                    if value_tag:
                        profile_info[mapped_key] = clean_text(value_tag.get_text(strip=True))
        
        return profile_info
    
    def _extract_section_contents(self, soup):
        """
        의약품 정보 섹션 내용 추출
        
        Args:
            soup: BeautifulSoup 객체
        
        Returns:
            dict: 추출된 섹션 내용
        """
        section_contents = {}
        
        # 섹션 찾기
        for section_name, key in MEDICINE_SECTIONS.items():
            # ID 패턴으로 섹션 찾기
            section_id = f"{MEDICINE_PATTERNS['content_section_id_prefix']}_{section_name}"
            section = soup.find(id=section_id)
            
            if section:
                # 텍스트 내용 추출
                text_element = section.find('div', class_=MEDICINE_PATTERNS['content_text_class'])
                if text_element:
                    section_contents[key] = clean_text(text_element.get_text(strip=True))
        
        return section_contents
    
    def _extract_image_url(self, soup):
        """
        의약품 이미지 URL 추출
        
        Args:
            soup: BeautifulSoup 객체
        
        Returns:
            str: 이미지 URL 또는 None
        """
        image_box = soup.find('div', class_=MEDICINE_PATTERNS['image_box_class'])
        
        if image_box:
            img_tag = image_box.find('img')
            if img_tag and 'src' in img_tag.attrs:
                # 상대 경로를 절대 경로로 변환
                return urllib.parse.urljoin('https://terms.naver.com', img_tag['src'])
        
        return None
    
    def _extract_english_name(self, soup):
        """
        영문명 추출
        
        Args:
            soup: BeautifulSoup 객체
        
        Returns:
            str: 영문명 또는 빈 문자열
        """
        english_name_tag = soup.find('span', class_=MEDICINE_PATTERNS['english_name_class'])
        
        if english_name_tag:
            return clean_text(english_name_tag.get_text(strip=True))
        
        return ''
    
    def parse_medicine_detail(self, soup, url):
        """
        약품 상세 페이지에서 정보 파싱
        
        Args:
            soup: BeautifulSoup 객체
            url: 페이지 URL
        
        Returns:
            dict: 파싱된 의약품 정보 또는 None
        """
        try:
            # 의약품사전 페이지인지 확인
            if not self.is_medicine_dictionary(soup, url):
                logger.warning(f"의약품사전 페이지가 아닙니다: {url}")
                return None
            
            # 제목(한글명) 추출
            title_tag = soup.find('h2', class_=MEDICINE_PATTERNS['title_class'])
            if not title_tag:
                logger.warning(f"약품명을 찾을 수 없음: {url}")
                return None
            
            korean_name = clean_text(title_tag.get_text(strip=True))
            
            # 데이터 추출
            medicine_data = {
                'korean_name': korean_name,
                'url': url
            }
            
            # 영문명 추출
            medicine_data['english_name'] = self._extract_english_name(soup)
            
            # 프로필 정보 추출
            medicine_data.update(self._extract_profile_info(soup))
            
            # 섹션 내용 추출
            medicine_data.update(self._extract_section_contents(soup))
            
            # 이미지 URL 추출
            medicine_data['image_url'] = self._extract_image_url(soup)
            
            # 해시 생성
            medicine_data['data_hash'] = generate_data_hash(medicine_data)
            
            return medicine_data
            
        except Exception as e:
            logger.error(f"의약품 정보 파싱 중 오류 발생: {url}, 오류: {e}", exc_info=True)
            return None
    
    def validate_medicine_data(self, medicine_data):
        """
        의약품 데이터 유효성 검사
        
        Args:
            medicine_data: 검증할 의약품 데이터
            
        Returns:
            dict: 유효성 검사 결과
        """
        # 기본 유효성 검사
        validation_result = {
            'is_valid': True,
            'reason': ''
        }
        
        # 필수 필드 확인
        if not medicine_data.get('korean_name'):
            validation_result['is_valid'] = False
            validation_result['reason'] = '한글명이 없음'
            return validation_result
        
        if not medicine_data.get('url'):
            validation_result['is_valid'] = False
            validation_result['reason'] = 'URL이 없음'
            return validation_result
        
        # 중요 정보 최소 개수 확인
        important_fields = ['efficacy', 'dosage', 'precautions']
        filled_count = sum(1 for field in important_fields if medicine_data.get(field))
        
        if filled_count < 2:
            validation_result['is_valid'] = False
            validation_result['reason'] = '중요 정보가 충분하지 않음'
            return validation_result
        
        # 모든 검사 통과
        return validation_result