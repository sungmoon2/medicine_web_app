import { fetchUrlContent } from '../utils/naverApi';
import { parseHtmlContent } from '../utils/htmlParser';

async function testMedicineExtraction(url: string) {
  try {
    // HTML 콘텐츠 가져오기
    const htmlContent = await fetchUrlContent(url);
    
    // HTML 파싱
    const result = parseHtmlContent(htmlContent, url);
    
    console.log('추출된 의약품 정보:', result.data);
    console.log('파싱 메타데이터:', result.meta);
  } catch (error) {
    console.error('테스트 중 오류:', error);
  }
}

// 테스트할 URL 입력 (네이버 의약품 사전 URL)
const testUrl = 'https://terms.naver.com/entry.naver?docId=XXXX';
testMedicineExtraction(testUrl);