#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
네이버 의약품 크롤러 프로젝트 구조 생성 스크립트
"""
import os
import shutil
from pathlib import Path

# 프로젝트 루트 디렉토리
ROOT_DIR = Path.cwd()

# 프로젝트 구조
PROJECT_STRUCTURE = {
    'config': {},
    'crawler': {},
    'db': {},
    'utils': {},
    'data': {
        'images': {},
        'json': {}
    },
    'checkpoints': {}
}

# 빈 __init__.py 파일 생성
INIT_FILES = [
    'config/__init__.py',
    'crawler/__init__.py',
    'db/__init__.py',
    'utils/__init__.py'
]

# 기본 파일 생성
EMPTY_FILES = [
    'config/settings.py',
    'crawler/api_client.py',
    'crawler/parser.py',
    'crawler/search_manager.py',
    'db/db_manager.py',
    'db/models.py',
    'utils/logger.py',
    'utils/helpers.py',
    'utils/file_handler.py',
    'main.py',
    '.env.example',
    'README.md'
]

def create_directory_structure(base_dir, structure):
    """
    디렉토리 구조 생성
    
    Args:
        base_dir: 기준 디렉토리
        structure: 생성할 디렉토리 구조
    """
    for dir_name, children in structure.items():
        dir_path = os.path.join(base_dir, dir_name)
        
        # 디렉토리 생성
        os.makedirs(dir_path, exist_ok=True)
        print(f"디렉토리 생성: {dir_path}")
        
        # 자식 디렉토리 생성
        if children:
            create_directory_structure(dir_path, children)

def create_empty_files(files):
    """
    빈 파일 생성
    
    Args:
        files: 생성할 파일 목록
    """
    for file_path in files:
        full_path = os.path.join(ROOT_DIR, file_path)
        
        # 디렉토리 확인
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # 빈 파일 생성
        if not os.path.exists(full_path):
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write("")
            print(f"파일 생성: {full_path}")
        else:
            print(f"파일 이미 존재: {full_path}")

def create_gitkeep_files():
    """빈 디렉토리에 .gitkeep 파일 생성"""
    for root, dirs, files in os.walk(ROOT_DIR):
        # .git 디렉토리 제외
        if '.git' in dirs:
            dirs.remove('.git')
        
        # 파일이 없는 디렉토리에 .gitkeep 추가
        if not files and root != str(ROOT_DIR):
            gitkeep_path = os.path.join(root, '.gitkeep')
            with open(gitkeep_path, 'w') as f:
                pass
            print(f".gitkeep 생성: {root}")

def create_env_example():
    """기본 .env.example 파일 생성"""
    env_example_path = os.path.join(ROOT_DIR, '.env.example')
    
    content = """# Naver API 설정
NAVER_CLIENT_ID=your_client_id_here
NAVER_CLIENT_SECRET=your_client_secret_here

# 데이터베이스 설정
DB_TYPE=sqlite  # sqlite 또는 mysql
DB_PATH=data/medicines.db  # SQLite 사용 시 DB 파일 경로

# MySQL/MariaDB 설정 (DB_TYPE=mysql인 경우 사용)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=medicine_db

# 크롤링 설정
MAX_RETRIES=3
REQUEST_DELAY=0.5
MAX_PAGES_PER_KEYWORD=10
DAILY_API_LIMIT=25000

# 체크포인트 설정
CHECKPOINT_INTERVAL=100  # 100개 항목마다 체크포인트 저장
CHECKPOINT_DIR=checkpoints

# 로깅 설정
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=naver_medicine_crawler.log
"""
    
    with open(env_example_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"파일 생성: {env_example_path}")

def create_readme():
    """기본 README.md 파일 생성"""
    readme_path = os.path.join(ROOT_DIR, 'README.md')
    
    content = """# 네이버 의약품 정보 크롤러

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
"""
    
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"파일 생성: {readme_path}")

def create_gitignore():
    """기본 .gitignore 파일 생성"""
    gitignore_path = os.path.join(ROOT_DIR, '.gitignore')
    
    content = """# 환경 변수 파일
.env
.env.*
!.env.example

# 데이터베이스 파일
*.db
*.sqlite
*.sqlite3

# 로그 파일
*.log
logs/

# 이미지 및 데이터 디렉토리
data/
checkpoints/

# 파이썬 캐시 파일
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE 설정 파일
.idea/
.vscode/
*.swp
*.swo
*.swn
.DS_Store
"""
    
    with open(gitignore_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"파일 생성: {gitignore_path}")

def create_requirements():
    """requirements.txt 파일 생성"""
    req_path = os.path.join(ROOT_DIR, 'requirements.txt')
    
    content = """beautifulsoup4==4.12.2
requests==2.31.0
python-dotenv==1.0.0
pymysql==1.1.0
tqdm==4.66.1
colorama==0.4.6
aiohttp==3.8.6
"""
    
    with open(req_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"파일 생성: {req_path}")

def main():
    """메인 함수"""
    print("네이버 의약품 크롤러 프로젝트 구조 생성 시작...")
    
    # 디렉토리 구조 생성
    create_directory_structure(ROOT_DIR, PROJECT_STRUCTURE)
    
    # 빈 파일 생성
    create_empty_files(INIT_FILES)
    create_empty_files(EMPTY_FILES)
    
    # .gitkeep 파일 생성
    create_gitkeep_files()
    
    # 예시 파일 생성
    create_env_example()
    create_readme()
    create_gitignore()
    create_requirements()
    
    print("\n프로젝트 구조 생성 완료!")
    print("\n다음 단계:")
    print("1. '.env.example'을 '.env'로 복사하고 Naver API 인증 정보 입력")
    print("2. 'pip install -r requirements.txt' 실행하여 필요한 패키지 설치")
    print("3. 'python main.py --all' 명령으로 크롤링 시작")

if __name__ == "__main__":
    main()