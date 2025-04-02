"""
HTML 파싱 모듈
"""
import re
import os
import hashlib
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
    
    def parse_medicine_detail(self, soup, url):
        """
        의약품 상세 페이지에서 정보 파싱 (개선된 버전)
        
        Args:
            soup: BeautifulSoup 객체
            url: 페이지 URL
        
        Returns:
            dict: 파싱된 의약품 정보 또는 None
        """
        try:
            # 1. 기본 유효성 검사는 유지
            if not self.is_medicine_dictionary(soup, url):
                logger.warning(f"[파싱 실패] 의약품사전 페이지가 아닙니다: {url}")
                
                # 디버깅용 HTML 저장
                self._save_debug_html(soup, url)
                
                return None
            
            # 2. 데이터 초기화
            medicine_data = {'url': url}
            
            # 3. size_ct_v2 div 태그 찾기 (주요 데이터 컨테이너)
            size_ct_div = soup.find('div', id='size_ct', class_='size_ct_v2')
            if not size_ct_div:
                # 다른 class명도 시도
                size_ct_div = soup.find('div', id='size_ct')
                if not size_ct_div:
                    logger.warning(f"[파싱 실패] size_ct div 태그를 찾을 수 없음: {url}")
                    
                    # 디버깅용 HTML 저장
                    self._save_debug_html(soup, url)
                    
                    return None
            
            # 4. 제목(한글명) 및 영문명 추출
            title_tag = soup.find('h2', class_='headword')
            english_name_tag = soup.find('span', class_='word_txt')
            
            if title_tag:
                medicine_data['korean_name'] = clean_text(title_tag.get_text())
            if english_name_tag:
                medicine_data['english_name'] = clean_text(english_name_tag.get_text())
            
            # 대안적 프로필 정보 추출 방법들
            profile_extraction_methods = [
                self._extract_profile_from_wrap,
                self._extract_profile_from_tmp,
                self._extract_profile_from_sections
            ]
            
            for extraction_method in profile_extraction_methods:
                if extraction_method(size_ct_div, medicine_data):
                    break
            
            # 6. 상세 섹션 내용 추출
            detail_extraction_methods = [
                self._extract_sections_from_div,
                self._extract_sections_from_alternative_selectors
            ]
            
            for extraction_method in detail_extraction_methods:
                if extraction_method(size_ct_div, medicine_data):
                    break
            
            # 7. 이미지 URL 추출
            img_extraction_methods = [
                self._extract_image_from_type_img,
                self._extract_image_from_alternative_selectors
            ]
            
            for extraction_method in img_extraction_methods:
                if extraction_method(size_ct_div, medicine_data):
                    break
            
            # 8. 데이터 해시 생성
            medicine_data['data_hash'] = generate_data_hash(medicine_data)
            
            # 9. 로깅: 추출된 필드 정보
            extracted_fields = [k for k, v in medicine_data.items() if v and k not in ['url', 'data_hash', 'image_url']]
            logger.info(f"[파싱 완료] {medicine_data.get('korean_name', 'Unknown')}: 총 {len(extracted_fields)}개 필드 추출, 필드: {', '.join(extracted_fields)}")
            
            return medicine_data
        
        except Exception as e:
            logger.error(f"[파싱 오류] 의약품 정보 파싱 중 오류 발생: {url}, 오류: {e}", exc_info=True)
            return None
    
    def _save_debug_html(self, soup, url):
        """
        디버깅용 HTML 저장
        
        Args:
            soup: BeautifulSoup 객체
            url: 페이지 URL
        """
        try:
            debug_dir = os.path.join(os.getcwd(), 'debug_html', 'medicine_pages')
            os.makedirs(debug_dir, exist_ok=True)
            
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            debug_file = os.path.join(debug_dir, f"{url_hash}_debug.html")
            
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            logger.debug(f"디버그 HTML 저장: {debug_file}")
        except Exception as e:
            logger.error(f"디버그 HTML 저장 중 오류: {e}")
    
    def _extract_profile_from_wrap(self, size_ct_div, medicine_data):
        """
        profile_wrap 클래스에서 프로필 정보 추출
        
        Args:
            size_ct_div: 메인 컨테이너 div
            medicine_data: 데이터를 저장할 딕셔너리
        
        Returns:
            bool: 추출 성공 여부
        """
        profile_div = size_ct_div.find('div', class_='profile_wrap')
        if not profile_div:
            return False
        
        dl_elements = profile_div.find_all('dl')
        for dl in dl_elements:
            dt_elements = dl.find_all('dt')
            dd_elements = dl.find_all('dd')
            
            for i in range(min(len(dt_elements), len(dd_elements))):
                field_name = clean_text(dt_elements[i].get_text())
                field_value = clean_text(dd_elements[i].get_text())
                
                # 프로필 필드 매핑
                for term, mapped_key in MEDICINE_PROFILE_ITEMS.items():
                    if term in field_name:
                        medicine_data[mapped_key] = field_value
        
        return len(medicine_data) > 1
    
    def _extract_profile_from_tmp(self, size_ct_div, medicine_data):
        """
        tmp_profile 클래스에서 프로필 정보 추출
        
        Args:
            size_ct_div: 메인 컨테이너 div
            medicine_data: 데이터를 저장할 딕셔너리
        
        Returns:
            bool: 추출 성공 여부
        """
        profile_div = size_ct_div.find('div', class_='tmp_profile')
        if not profile_div:
            return False
        
        dt_elements = profile_div.find_all('dt')
        dd_elements = profile_div.find_all('dd')
        
        for i in range(min(len(dt_elements), len(dd_elements))):
            field_name = clean_text(dt_elements[i].get_text())
            field_value = clean_text(dd_elements[i].get_text())
            
            # 프로필 필드 매핑
            for term, mapped_key in MEDICINE_PROFILE_ITEMS.items():
                if term in field_name:
                    medicine_data[mapped_key] = field_value
        
        return len(medicine_data) > 1
    
    def _extract_profile_from_sections(self, size_ct_div, medicine_data):
        """
        대안적 섹션에서 프로필 정보 추출
        
        Args:
            size_ct_div: 메인 컨테이너 div
            medicine_data: 데이터를 저장할 딕셔너리
        
        Returns:
            bool: 추출 성공 여부
        """
        alternate_profile_sections = [
            size_ct_div.find('div', class_='profile_info'),
            size_ct_div.find('div', id='profile_section')
        ]
        
        for alt_profile in alternate_profile_sections:
            if alt_profile:
                profile_items = alt_profile.find_all(['dt', 'dd'])
                for i in range(0, len(profile_items), 2):
                    if i+1 < len(profile_items):
                        key = clean_text(profile_items[i].get_text())
                        value = clean_text(profile_items[i+1].get_text())
                        
                        # 키워드 매핑 확장
                        for pattern, mapped_key in MEDICINE_PROFILE_ITEMS.items():
                            if pattern in key:
                                medicine_data[mapped_key] = value
        
        return len(medicine_data) > 1
    
    def _extract_sections_from_div(self, size_ct_div, medicine_data):
        """
        기본 섹션 추출
        
        Args:
            size_ct_div: 메인 컨테이너 div
            medicine_data: 데이터를 저장할 딕셔너리
        
        Returns:
            bool: 추출 성공 여부
        """
        sections = size_ct_div.find_all('div', class_='section')
        for section in sections:
            # 섹션 제목 찾기
            section_title_tag = section.find('h3')
            if not section_title_tag:
                continue
            
            section_title = clean_text(section_title_tag.get_text())
            
            # 섹션 내용 찾기 (다양한 선택자 시도)
            content_selectors = [
                section.find('div', class_='content'),
                section.find('p', class_='txt'),
                section.find('div', class_='txt')
            ]
            
            for content_tag in content_selectors:
                if content_tag:
                    section_content = clean_text(content_tag.get_text())
                    
                    # 섹션 매핑
                    for term, mapped_key in MEDICINE_SECTIONS.items():
                        if term in section_title:
                            medicine_data[mapped_key] = section_content
                            break
                    break
        
        return len(medicine_data) > 1
    
    def _extract_sections_from_alternative_selectors(self, size_ct_div, medicine_data):
        """
        대안적 섹션 선택자로 내용 추출
        
        Args:
            size_ct_div: 메인 컨테이너 div
            medicine_data: 데이터를 저장할 딕셔너리
        
        Returns:
            bool: 추출 성공 여부
        """
        alternate_section_selectors = [
            {'selector': 'div.section_content', 'title_tag': 'h4'},
            {'selector': 'div.detail_section', 'title_tag': 'h3'},
            {'selector': 'div.medicine_info', 'title_tag': 'h2'}
        ]
        
        for section_config in alternate_section_selectors:
            sections = size_ct_div.find_all(
                'div', 
                class_=section_config['selector'].split('.')[-1]
            )
            
            for section in sections:
                title_tag = section.find(section_config['title_tag'])
                if title_tag:
                    section_title = clean_text(title_tag.get_text())
                    content_tag = section.find(['p', 'div'], class_=['txt', 'content'])
                    
                    if content_tag:
                        content = clean_text(content_tag.get_text())
                        for term, mapped_key in MEDICINE_SECTIONS.items():
                            if term in section_title:
                                medicine_data[mapped_key] = content
                                break
        
        return len(medicine_data) > 1
    
    def _extract_image_from_type_img(self, size_ct_div, medicine_data):
        """
        type_img 클래스 이미지 추출
        
        Args:
            size_ct_div: 메인 컨테이너 div
            medicine_data: 데이터를 저장할 딕셔너리
        
        Returns:
            bool: 추출 성공 여부
        """
        img_tag = size_ct_div.find('img', class_='type_img')
        if img_tag and 'src' in img_tag.attrs:
            medicine_data['image_url'] = urllib.parse.urljoin('https://terms.naver.com', img_tag['src'])
            return True
        
        return False
    
    def _extract_image_from_alternative_selectors(self, size_ct_div, medicine_data):
        """
        대안적 이미지 선택자로 URL 추출
        
        Args:
            size_ct_div: 메인 컨테이너 div
            medicine_data: 데이터를 저장할 딕셔너리
        
        Returns:
            bool: 추출 성공 여부
        """
        image_selectors = [
            size_ct_div.find('div', class_='img_box'),
            size_ct_div.find('img', class_='medicine_img'),
            size_ct_div.find('div', id='medicine_image_section')
        ]
        
        for img_section in image_selectors:
            if img_section:
                img_tag = img_section.find('img')
                if img_tag and 'src' in img_tag.attrs:
                    medicine_data['image_url'] = urllib.parse.urljoin('https://terms.naver.com', img_tag['src'])
                    return True
        
        return False
    
    def is_medicine_dictionary(self, soup, url):
        """
        HTML이 의약품사전 페이지인지 확인 (간소화된 버전)
        
        Args:
            soup: BeautifulSoup 객체
            url: 페이지 URL
        
        Returns:
            bool: 의약품사전이면 True
        """
        # 1. URL 패턴 확인 - cid=51000이 필수 조건
        if 'cid=51000' not in url or 'terms.naver.com/entry.naver' not in url:
            logger.debug(f"URL 패턴 불일치: {url}")
            return False
        
        # 2. 리다이렉트 감지 - 페이지 제목 확인
        title_tag = soup.find('title')
        if not title_tag or '네이버 지식백과' in title_tag.text and '의약품사전' not in title_tag.text:
            logger.debug(f"리다이렉트된 페이지 또는 제목 불일치: {url}")
            return False
        
        # 3. 간단한 페이지 구조 확인 - headword(제목) 태그가 있는지만 확인
        headword = soup.find('h2', class_='headword')
        if not headword:
            logger.debug(f"제목 태그 없음: {url}")
            return False
        
        # 4. 의약품사전 키워드 포함 여부 확인
        has_medicine_keyword = False
        
        # 방법 1: cite 태그 확인
        cite_tag = soup.find('p', class_='cite')
        if cite_tag and '의약품사전' in cite_tag.get_text():
            has_medicine_keyword = True
        
        # 방법 2: 메타 태그 확인
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            if tag.get('content') and '의약품' in tag.get('content'):
                has_medicine_keyword = True
                break
        
        if not has_medicine_keyword:
            logger.debug(f"의약품 키워드 없음: {url}")
            return False
        
        logger.info(f"유효한 의약품 페이지 확인: {url}")
        return True