"""
데이터 모델 클래스
"""
from datetime import datetime
from utils.helpers import generate_data_hash

class Medicine:
    """의약품 정보 모델"""
    
    def __init__(self, **kwargs):
        """
        의약품 객체 초기화
        
        Args:
            **kwargs: 의약품 속성
        """
        # 기본 속성 설정
        self.id = kwargs.get('id')
        self.korean_name = kwargs.get('korean_name', '')
        self.english_name = kwargs.get('english_name', '')
        self.category = kwargs.get('category', '')
        self.type = kwargs.get('type', '')
        self.company = kwargs.get('company', '')
        self.appearance = kwargs.get('appearance', '')
        self.insurance_code = kwargs.get('insurance_code', '')
        self.shape = kwargs.get('shape', '')
        self.color = kwargs.get('color', '')
        self.size = kwargs.get('size', '')
        self.identification = kwargs.get('identification', '')
        self.components = kwargs.get('components', '')
        self.efficacy = kwargs.get('efficacy', '')
        self.precautions = kwargs.get('precautions', '')
        self.dosage = kwargs.get('dosage', '')
        self.storage = kwargs.get('storage', '')
        self.period = kwargs.get('period', '')
        self.image_url = kwargs.get('image_url', '')
        self.image_path = kwargs.get('image_path', '')
        self.url = kwargs.get('url', '')
        self.created_at = kwargs.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self.updated_at = kwargs.get('updated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        self.data_hash = kwargs.get('data_hash', '')
        
        # 추가 속성이 있으면 동적으로 추가
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
        
        # 데이터 해시가 없으면 생성
        if not self.data_hash:
            self.generate_hash()
    
    def generate_hash(self):
        """데이터 해시 생성"""
        self.data_hash = generate_data_hash(self.to_dict())
    
    def to_dict(self):
        """
        객체를 딕셔너리로 변환
        
        Returns:
            dict: 의약품 정보를 담은 딕셔너리
        """
        result = {}
        for key, value in self.__dict__.items():
            # 프라이빗 속성은 제외
            if not key.startswith('_'):
                result[key] = value
        return result
    
    def from_dict(self, data):
        """
        딕셔너리에서 객체 속성 설정
        
        Args:
            data: 설정할 데이터 딕셔너리
            
        Returns:
            Medicine: 자기 자신
        """
        for key, value in data.items():
            setattr(self, key, value)
        return self
    
    def is_valid(self):
        """
        유효성 검사
        
        Returns:
            bool: 유효하면 True
        """
        # 필수 필드 검사
        if not self.korean_name or not self.url:
            return False
        
        # 최소한의 중요 정보가 있는지 확인
        important_fields = ['english_name', 'company', 'efficacy', 'dosage', 'precautions']
        filled_count = sum(1 for field in important_fields if getattr(self, field))
        
        # 중요 필드 중 최소 2개 이상이 채워져 있어야 함
        if filled_count < 2:
            return False
        
        return True
    
    def __str__(self):
        """문자열 표현"""
        return f"Medicine(id={self.id}, name={self.korean_name})"
    
    def __repr__(self):
        """개발자용 표현"""
        return self.__str__()


class ApiCall:
    """API 호출 기록 모델"""
    
    def __init__(self, date=None, count=0):
        """
        API 호출 기록 초기화
        
        Args:
            date: 날짜 (None이면 오늘)
            count: 호출 횟수
        """
        self.id = None
        self.date = date or datetime.now().strftime('%Y-%m-%d')
        self.count = count
        self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def to_dict(self):
        """
        객체를 딕셔너리로 변환
        
        Returns:
            dict: API 호출 정보를 담은 딕셔너리
        """
        return {
            'id': self.id,
            'date': self.date,
            'count': self.count,
            'created_at': self.created_at
        }
    
    def from_dict(self, data):
        """
        딕셔너리에서 객체 속성 설정
        
        Args:
            data: 설정할 데이터 딕셔너리
            
        Returns:
            ApiCall: 자기 자신
        """
        for key, value in data.items():
            setattr(self, key, value)
        return self
    
    def __str__(self):
        """문자열 표현"""
        return f"ApiCall(date={self.date}, count={self.count})"
    
    def __repr__(self):
        """개발자용 표현"""
        return self.__str__()