# 네이버 의약품 정보 크롤러

네이버 지식백과 - 의약품사전에 등록된 의약품 정보를 수집하는 Python 크롤러입니다.

## 기능

- 네이버 검색 API를 활용한 의약품 검색
- 의약품 상세 페이지 파싱
- 데이터베이스 저장 (SQLite 또는 MySQL)
- 이미지 다운로드
- 체크포인트 기능
- 중복 검사
- 로깅

## 설치 및 설정

1. 요구사항 설치:
   ```
   pip install -r requirements.txt
   ```

2. 환경 변수 설정:
   - `.env.example`를 `.env`로 복사하고 필요한 정보 입력
   - 네이버 API 키 설정: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`

## 사용법

```bash
# 모든 키워드로 검색
python main.py --all

# 특정 키워드로 검색
python main.py --keyword "타이레놀"

# 특정 URL에서 정보 수집
python main.py --url "https://terms.naver.com/entry.naver?docId=XXXX"

# 데이터베이스 통계 출력
python main.py --stats

# 데이터 내보내기
python main.py --export --output medicines.json

# 체크포인트에서 계속
python main.py --continue
```

## 프로젝트 구조

```
naver_medicine_crawler/
│
├── .env                      # API 키, DB 설정 등 환경변수
├── .env.example              # 환경변수 예시 파일
├── .gitignore                # Git 제외 파일 목록
│
├── main.py                   # 메인 실행 파일
│
├── config/
│   └── settings.py           # 설정 관련 모듈
│
├── crawler/
│   ├── api_client.py         # 네이버 API 호출 클라이언트
│   ├── parser.py             # HTML 파싱 모듈
│   └── search_manager.py     # 검색 및 크롤링 관리 모듈
│
├── db/
│   ├── db_manager.py         # 데이터베이스 관리 모듈
│   └── models.py             # 데이터 모델 클래스
│
├── utils/
│   ├── logger.py             # 로깅 유틸리티
│   ├── file_handler.py       # 파일 처리 유틸리티  
│   └── helpers.py            # 기타 헬퍼 함수
│
├── checkpoints/              # 체크포인트 저장 디렉토리
│   └── .gitkeep
│
└── data/                     # 수집 데이터 저장 디렉토리
    ├── images/               # 의약품 이미지 저장 디렉토리
    └── json/                 # JSON 형식 데이터 저장 디렉토리
```
