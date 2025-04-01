// src/types/medicine.ts

// 의약품 기본 정보 인터페이스
export interface Medicine {
    id: number;
    korean_name: string;
    english_name: string;
    url: string;
    category: string;
    company: string;
  }
  
  // 의약품 상세 정보 인터페이스
  export interface MedicineDetails {
    database_details: any;
    original_url: string;
    html_preview?: string;
  }
  
  // 검증 결과 인터페이스
  export interface ValidationResult {
    details: any;
    validation: Record<string, boolean>;
    extraction_completeness: number;
  }