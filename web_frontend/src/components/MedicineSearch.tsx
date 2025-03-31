import React, { useState, useEffect } from 'react';
import { fetchNaverSearchResults, fetchUrlContent } from '../utils/naverApi';
import { parseHtmlContent } from '../utils/htmlParser'; // 파서 유틸리티 필요

interface SearchResult {
  title: string;
  link: string;
  description: string;
}

const MedicineSearch: React.FC = () => {
  const [keyword, setKeyword] = useState('타이레놀');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedMedicine, setSelectedMedicine] = useState<any>(null);

  const handleSearch = async () => {
    try {
      const results = await fetchNaverSearchResults(keyword);
      setSearchResults(results);
    } catch (error) {
      console.error('검색 실패:', error);
    }
  };

  const fetchMedicineDetails = async (url: string) => {
    try {
      const htmlContent = await fetchUrlContent(url);
      const parsedData = parseHtmlContent(htmlContent);
      setSelectedMedicine(parsedData);
    } catch (error) {
      console.error('의약품 상세 정보 가져오기 실패:', error);
    }
  };

  return (
    <div className="p-4">
      <div className="flex mb-4">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="border p-2 mr-2 flex-grow"
          placeholder="의약품 키워드 입력"
        />
        <button 
          onClick={handleSearch} 
          className="bg-blue-500 text-white px-4 py-2"
        >
          검색
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* 검색 결과 목록 */}
        <div>
          <h2 className="text-xl font-bold mb-2">검색 결과</h2>
          {searchResults.map((result, index) => (
            <div 
              key={index} 
              className="border p-2 mb-2 cursor-pointer hover:bg-gray-100"
              onClick={() => fetchMedicineDetails(result.link)}
            >
              <h3 dangerouslySetInnerHTML={{ __html: result.title }} />
              <p>{result.description}</p>
            </div>
          ))}
        </div>

        {/* 선택된 의약품 상세 정보 */}
        <div>
          <h2 className="text-xl font-bold mb-2">의약품 상세 정보</h2>
          {selectedMedicine && (
            <div className="border p-4">
              <pre>{JSON.stringify(selectedMedicine, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MedicineSearch;