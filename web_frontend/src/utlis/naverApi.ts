import axios from 'axios';

export interface SearchResult {
  title: string;
  link: string;
  description: string;
}

export const fetchNaverSearchResults = async (keyword: string): Promise<SearchResult[]> => {
  try {
    // 임시 더미 데이터 (실제 API 호출 전 테스트용)
    return [
      {
        title: '타이레놀 의약품 정보',
        link: 'https://example.com/medicine/tylenol',
        description: '해열 진통제'
      }
    ];
  } catch (error) {
    console.error('검색 중 오류:', error);
    return [];
  }
};

export const fetchUrlContent = async (url: string): Promise<string> => {
  try {
    // 임시 더미 데이터
    return '<html><body>의약품 정보</body></html>';
  } catch (error) {
    console.error('URL 콘텐츠 가져오기 실패:', error);
    return '';
  }
};