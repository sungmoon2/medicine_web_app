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
  imageUrl?: string;
}

export const parseHtmlContent = (htmlContent: string): MedicineInfo => {
  const $ = load(htmlContent);
  const medicineInfo: MedicineInfo = {};

  try {
    // 한글명 추출 (헤더에서)
    medicineInfo.koreanName = $('.headword').first().text().trim();

    // 영문명 추출
    medicineInfo.englishName = $('.word_txt').first().text().trim();

    // 프로필 정보 추출
    $('.tmp_profile dt').each((i, elem) => {
      const label = $(elem).text().trim();
      const value = $(elem).next('dd').text().trim();

      switch(label) {
        case '분류':
          medicineInfo.category = value;
          break;
        case '업체명':
          medicineInfo.company = value;
          break;
        case '성상':
          medicineInfo.appearance = value;
          break;
      }
    });

    // 효능효과 추출
    const efficacySection = $('div[id^="TABLE_OF_CONTENT_효능효과"]');
    medicineInfo.efficacy = efficacySection.find('.txt').text().trim();

    // 용법용량 추출
    const dosageSection = $('div[id^="TABLE_OF_CONTENT_용법용량"]');
    medicineInfo.dosage = dosageSection.find('.txt').text().trim();

    // 주의사항 추출
    const precautionsSection = $('div[id^="TABLE_OF_CONTENT_주의사항"]');
    medicineInfo.precautions = precautionsSection.find('.txt').text().trim();

    // 이미지 URL 추출
    const imageElement = $('.img_box img');
    if (imageElement.length) {
      medicineInfo.imageUrl = imageElement.attr('src');
    }

  } catch (error) {
    console.error('HTML 파싱 중 오류:', error);
  }

  return medicineInfo;
};