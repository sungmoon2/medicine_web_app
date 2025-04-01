import axios from 'axios';

export const fetchUrlContent = async (url: string): Promise<string> => {
  try {
    // FastAPI 백엔드의 엔드포인트 호출
    const response = await axios.get(`http://localhost:8000/api/medicine/url?url=${encodeURIComponent(url)}`);
    return response.data.html_preview || '';
  } catch (error) {
    console.error('URL 콘텐츠 가져오기 실패:', error);
    return '';
  }
};

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