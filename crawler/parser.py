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
                return None
            
            # 2. 데이터 초기화
            medicine_data = {'url': url}
            
            # 3. size_ct_v2 div 태그 찾기 (주요 데이터 컨테이너)
            size_ct_div = soup.find('div', id='size_ct', class_='size_ct_v2')
            if not size_ct_div:
                logger.warning(f"[파싱 실패] size_ct_v2 div 태그를 찾을 수 없음: {url}")
                return None
            
            # 4. 제목(한글명) 및 영문명 추출
            title_tag = soup.find('h2', class_='headword')
            english_name_tag = soup.find('span', class_='word_txt')
            
            if title_tag:
                medicine_data['korean_name'] = clean_text(title_tag.get_text())
            if english_name_tag:
                medicine_data['english_name'] = clean_text(english_name_tag.get_text())
            
            # 5. 프로필 정보 추출 (세부 정보 컬럼)
            profile_div = size_ct_div.find('div', class_='profile_wrap')
            if profile_div:
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
                                break
            
            # 6. 상세 섹션 내용 추출
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
            
            # 7. 이미지 URL 추출
            img_tag = size_ct_div.find('img', class_='type_img')
            if img_tag and 'src' in img_tag.attrs:
                medicine_data['image_url'] = urllib.parse.urljoin('https://terms.naver.com', img_tag['src'])
            
            # 8. 데이터 해시 생성
            medicine_data['data_hash'] = generate_data_hash(medicine_data)
            
            # 9. 로깅: 추출된 필드 정보
            extracted_fields = [k for k, v in medicine_data.items() if v and k not in ['url', 'data_hash', 'image_url']]
            logger.info(f"[파싱 완료] {medicine_data.get('korean_name', 'Unknown')}: 총 {len(extracted_fields)}개 필드 추출, 필드: {', '.join(extracted_fields)}")
            
            return medicine_data
        
        except Exception as e:
            logger.error(f"[파싱 오류] 의약품 정보 파싱 중 오류 발생: {url}, 오류: {e}", exc_info=True)
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
        
        # 중요 정보 최소 개수 확인 (기준 완화)
        # 이전: 중요 정보 중 2개 이상 필요
        # 변경: 중요 정보 중 1개 이상 필요
        important_fields = ['efficacy', 'dosage', 'precautions', 'components', 'category', 'company']
        filled_count = sum(1 for field in important_fields if medicine_data.get(field))
        
        if filled_count < 1:  # 1개 이상의 중요 정보 필요
            validation_result['is_valid'] = False
            validation_result['reason'] = '중요 정보가 충분하지 않음'
            
            # 누락된 중요 필드 목록 추가
            missing_fields = [field for field in important_fields if not medicine_data.get(field)]
            validation_result['missing_fields'] = missing_fields
            
            return validation_result
        
        # 모든 검사 통과
        return validation_result