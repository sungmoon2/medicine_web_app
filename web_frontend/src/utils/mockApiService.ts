// src/utlis/mockApiService.ts
import { Medicine, MedicineDetails, ValidationResult } from '../types/medicine';

// 의약품 목록 모의 데이터
const mockMedicines: Medicine[] = [
  {
    id: 1,
    korean_name: '타이레놀',
    english_name: 'Tylenol',
    url: 'https://example.com/medicine/tylenol',
    category: '해열진통제',
    company: '한국얀센'
  },
  {
    id: 2,
    korean_name: '어린이 타이레놀',
    english_name: 'Children\'s Tylenol',
    url: 'https://example.com/medicine/childrens-tylenol',
    category: '해열진통제',
    company: '한국얀센'
  },
  {
    id: 3,
    korean_name: '아스피린',
    english_name: 'Aspirin',
    url: 'https://example.com/medicine/aspirin',
    category: '해열진통제',
    company: '바이엘'
  },
  {
    id: 4,
    korean_name: '판콜에이',
    english_name: 'Pancol-A',
    url: 'https://example.com/medicine/pancol',
    category: '종합감기약',
    company: '동화약품'
  },
  {
    id: 5,
    korean_name: '게보린',
    english_name: 'Geworin',
    url: 'https://example.com/medicine/geworin',
    category: '해열진통제',
    company: '삼진제약'
  }
];

// 의약품 상세 정보 모의 데이터
const getMockMedicineDetails = (url: string): MedicineDetails => {
  const medicine = mockMedicines.find(med => med.url === url) || mockMedicines[0];
  
  return {
    database_details: {
      ...medicine,
      appearance: '흰색 타원형 정제',
      efficacy: '두통, 치통, 발열, 관절통, 근육통의 완화',
      dosage: '성인 1회 1~2정, 1일 3~4회 복용',
      precautions: '임신 중이거나 간 질환이 있는 환자는 의사와 상담 후 복용하십시오.',
    },
    original_url: url,
    html_preview: `<div class="medicine-info">
      <h1 class="headword">${medicine.korean_name}</h1>
      <p class="word_txt">${medicine.english_name}</p>
      <div class="tmp_profile">
        <dt>분류</dt><dd>${medicine.category}</dd>
        <dt>업체명</dt><dd>${medicine.company}</dd>
      </div>
    </div>`
  };
};

// 의약품 검증 결과 모의 데이터
const getMockValidationResult = (url: string): ValidationResult => {
  return {
    details: {
      korean_name: '타이레놀',
      english_name: 'Tylenol',
      category: '해열진통제',
      company: '한국얀센',
      appearance: '흰색 타원형 정제',
      efficacy: '두통, 치통, 발열, 관절통, 근육통의 완화',
      dosage: '성인 1회 1~2정, 1일 3~4회 복용',
      precautions: '임신 중이거나 간 질환이 있는 환자는 의사와 상담 후 복용하십시오.'
    },
    validation: {
      korean_name: true,
      english_name: true,
      category: true,
      company: true,
      appearance: true,
      efficacy: false, // 일부러 검증 실패 예시
      dosage: true,
      precautions: false // 일부러 검증 실패 예시
    },
    extraction_completeness: 0.75 // 75% 완전성
  };
};

// API 호출 모의 함수
export const fetchMedicines = async (): Promise<{ medicines: Medicine[] }> => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({ medicines: mockMedicines });
    }, 500); // 500ms 지연으로 API 호출 시뮬레이션
  });
};

export const fetchMedicineByUrl = async (url: string): Promise<MedicineDetails> => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(getMockMedicineDetails(url));
    }, 700);
  });
};

export const validateMedicineExtraction = async (url: string): Promise<ValidationResult> => {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve(getMockValidationResult(url));
    }, 800);
  });
};