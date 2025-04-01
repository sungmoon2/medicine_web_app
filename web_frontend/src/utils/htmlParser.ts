import { load } from 'cheerio';

// 의약품 정보 인터페이스
export interface MedicineInfo {
  koreanName?: string;
  englishName?: string;
  category?: string;
  company?: string;
  appearance?: string;
  efficacy?: string;
  dosage?: string;
  precautions?: string;
  sideEffects?: string;
  interactions?: string;
  storageMethod?: string;
  pregnancyInfo?: string;
  childrenInfo?: string;
  elderlyInfo?: string;
  drugCode?: string;
  ingredients?: string[];
  formulation?: string;
  imageUrl?: string;
  referenceUrls?: string[];
  lastUpdated?: string;
}

// 파싱 결과 타입
export interface ParsedResult {
  data: MedicineInfo;
  meta: {
    sourceUrl: string;
    parsingSuccess: boolean;
    extractedFields: string[];
    missingFields: string[];
    parsingErrors?: string[];
    completeness: number;
  };
}

// 모든 가능한 MedicineInfo 필드를 배열로 정의
const MEDICINE_INFO_FIELDS = [
  'koreanName', 'englishName', 'category', 'company', 'appearance', 
  'efficacy', 'dosage', 'precautions', 'sideEffects', 'interactions', 'storageMethod',
  'pregnancyInfo', 'childrenInfo', 'elderlyInfo', 
  'drugCode', 'ingredients', 'formulation',
  'imageUrl', 'referenceUrls', 'lastUpdated'
];

// HTML 콘텐츠 파싱 함수 (url 매개변수를 선택적으로 받음)
export const parseHtmlContent = (htmlContent: string, sourceUrl: string = ''): ParsedResult => {
  const $ = load(htmlContent);
  const medicineInfo: MedicineInfo = {};
  
  // 파싱 메타데이터 초기화
  const meta = {
    sourceUrl,
    parsingSuccess: false,
    extractedFields: [] as string[],
    missingFields: [] as string[],
    parsingErrors: [] as string[],
    completeness: 0
  };

  try {
    // 한글명 추출 (헤더에서)
    const koreanName = $('.headword, .drug-title, h1.title').first().text().trim();
    if (koreanName) {
      medicineInfo.koreanName = koreanName;
      meta.extractedFields.push('koreanName');
    }

    // 영문명 추출
    const englishName = $('.word_txt, .eng-title, .drug-eng-name').first().text().trim();
    if (englishName) {
      medicineInfo.englishName = englishName;
      meta.extractedFields.push('englishName');
    }

    // 프로필 정보 추출
    $('.tmp_profile dt, .profile-item dt').each((i, elem) => {
      const label = $(elem).text().trim();
      const value = $(elem).next('dd').text().trim();

      if (value) {
        switch(label) {
          case '분류':
            medicineInfo.category = value;
            meta.extractedFields.push('category');
            break;
          case '업체명':
          case '제조사':
            medicineInfo.company = value;
            meta.extractedFields.push('company');
            break;
          case '성상':
            medicineInfo.appearance = value;
            meta.extractedFields.push('appearance');
            break;
        }
      }
    });

    // 효능효과 추출
    const efficacy = $('div[id^="TABLE_OF_CONTENT_효능효과"] .txt, .section-efficacy .content, #efficacy').text().trim();
    if (efficacy) {
      medicineInfo.efficacy = efficacy;
      meta.extractedFields.push('efficacy');
    }

    // 용법용량 추출
    const dosage = $('div[id^="TABLE_OF_CONTENT_용법용량"] .txt, .section-dosage .content, #dosage').text().trim();
    if (dosage) {
      medicineInfo.dosage = dosage;
      meta.extractedFields.push('dosage');
    }

    // 주의사항 추출
    const precautions = $('div[id^="TABLE_OF_CONTENT_주의사항"] .txt, .section-precautions .content, #precautions').text().trim();
    if (precautions) {
      medicineInfo.precautions = precautions;
      meta.extractedFields.push('precautions');
    }
    
    // 이상반응 추출
    const sideEffects = $('div[id^="TABLE_OF_CONTENT_이상반응"] .txt, .section-side-effects, #side-effects').text().trim();
    if (sideEffects) {
      medicineInfo.sideEffects = sideEffects;
      meta.extractedFields.push('sideEffects');
    }

    // 상호작용 추출
    const interactions = $('div[id^="TABLE_OF_CONTENT_상호작용"] .txt, .section-interactions, #interactions').text().trim();
    if (interactions) {
      medicineInfo.interactions = interactions;
      meta.extractedFields.push('interactions');
    }

    // 이미지 URL 추출
    const imageElement = $('.img_box img, .drug-image img, .medicine-image');
    if (imageElement.length) {
      medicineInfo.imageUrl = imageElement.attr('src');
      meta.extractedFields.push('imageUrl');
    }

    // 파싱 성공 여부 및 완전성 계산
    meta.missingFields = MEDICINE_INFO_FIELDS.filter(field => 
      !medicineInfo[field as keyof MedicineInfo]
    );
    meta.parsingSuccess = meta.extractedFields.length > 0;
    meta.completeness = meta.extractedFields.length / MEDICINE_INFO_FIELDS.length;
    
  } catch (error) {
    console.error('HTML 파싱 중 오류:', error);
    meta.parsingErrors.push((error as Error).message);
    meta.parsingSuccess = false;
  }

  return { data: medicineInfo, meta };
};