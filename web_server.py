import os
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리를 sys.path에 추가
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# 프로젝트 모듈 임포트
from db.db_manager import DatabaseManager
from crawler.api_client import NaverAPIClient

# FastAPI 애플리케이션 생성
app = FastAPI(title="Medicine Crawler Viewer")

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프론트엔드 개발 시 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터베이스 관리자 초기화
db_manager = DatabaseManager()
api_client = NaverAPIClient(db_manager)

@app.get("/api/medicines")
def list_medicines(limit: int = 100, offset: int = 0):
    """
    의약품 목록 조회
    """
    medicines = db_manager.get_all_medicines_with_details(limit, offset)
    return {
        "total": len(medicines),
        "medicines": medicines
    }

@app.get("/api/medicine/url")
def get_medicine_by_url(url: str):
    """
    특정 URL의 의약품 상세 정보 조회
    """
    medicine_details = db_manager.get_medicine_details_by_url(url)
    
    if not medicine_details:
        raise HTTPException(status_code=404, detail="의약품을 찾을 수 없습니다.")
    
    # 원본 URL 데이터 가져오기
    try:
        html_content = api_client.get_html_content(url)
        return {
            "database_details": medicine_details,
            "original_url": url,
            "html_preview": html_content[:1000] + "..." if html_content else None
        }
    except Exception as e:
        return {
            "database_details": medicine_details,
            "original_url": url,
            "html_preview": None,
            "error": str(e)
        }

@app.get("/api/medicine/validate-extraction/{url:path}")
def validate_data_extraction(url: str):
    """
    데이터 추출 검증
    """
    medicine_details = db_manager.get_medicine_details_by_url(url)
    
    if not medicine_details:
        raise HTTPException(status_code=404, detail="의약품을 찾을 수 없습니다.")
    
    # 주요 필드 검증
    validation_results = {
        "korean_name": bool(medicine_details.get("korean_name")),
        "english_name": bool(medicine_details.get("english_name")),
        "category": bool(medicine_details.get("category")),
        "company": bool(medicine_details.get("company")),
        "appearance": bool(medicine_details.get("appearance")),
        "components": bool(medicine_details.get("components")),
        "efficacy": bool(medicine_details.get("efficacy")),
        "precautions": bool(medicine_details.get("precautions")),
        "dosage": bool(medicine_details.get("dosage")),
        "image_url": bool(medicine_details.get("image_url")),
    }
    
    return {
        "details": medicine_details,
        "validation": validation_results,
        "extraction_completeness": sum(validation_results.values()) / len(validation_results)
    }

# 정적 파일 서빙 (프론트엔드 빌드 디렉토리)
app.mount("/", StaticFiles(directory="web_frontend/build", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)