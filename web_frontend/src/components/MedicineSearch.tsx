import React, { useState } from 'react';
import { fetchNaverSearchResults, fetchUrlContent } from '../utils/naverApi';
import { parseHtmlContent, MedicineInfo } from '../utils/htmlParser';
import { Search, AlertCircle, CheckCircle, Download } from 'lucide-react';

// 파싱 결과 타입 정의
interface ParsedResult {
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

interface SearchResult {
  title: string;
  link: string;
  description: string;
}

const MedicineSearch: React.FC = () => {
  const [keyword, setKeyword] = useState('타이레놀');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedMedicine, setSelectedMedicine] = useState<MedicineInfo | null>(null);
  const [medicineMetadata, setMedicineMetadata] = useState<ParsedResult['meta'] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'info' | 'meta'>('info');

  const handleSearch = async () => {
    if (!keyword.trim()) {
      setError('검색어를 입력해주세요.');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const results = await fetchNaverSearchResults(keyword);
      setSearchResults(results);
      setIsLoading(false);
    } catch (error) {
      console.error('검색 실패:', error);
      setError('검색 중 오류가 발생했습니다.');
      setIsLoading(false);
    }
  };

  const fetchMedicineDetails = async (url: string, title: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      // HTML 컨텐츠 가져오기
      const htmlContent = await fetchUrlContent(url);
      
      // HTML 파싱 - parseHtmlContent가 이제 ParsedResult 타입을 반환한다고 가정
      // 방법 1: htmlParser.ts가 업데이트된 경우 (url 파라미터를 받을 수 있음)
      const result = parseHtmlContent(htmlContent, url);
      
      // 방법 2: htmlParser.ts가 업데이트되지 않은 경우 (수동으로 결과 구성)
      /*
      const parsedInfo = parseHtmlContent(htmlContent);
      
      const result = {
        data: parsedInfo,
        meta: {
          sourceUrl: url,
          parsingSuccess: true,
          extractedFields: Object.keys(parsedInfo).filter(key => 
            parsedInfo[key as keyof typeof parsedInfo] !== undefined && 
            parsedInfo[key as keyof typeof parsedInfo] !== ''
          ),
          missingFields: [],
          completeness: 0.5 // 기본값
        }
      };
      */
      
      // 타이틀이 있고 약 이름이 없으면 타이틀을 이름으로 사용
      if (title && !result.data.koreanName) {
        result.data.koreanName = title.replace(/<[^>]*>/g, '');
        if (!result.meta.extractedFields.includes('koreanName')) {
          result.meta.extractedFields.push('koreanName');
        }
      }
      
      // 상태 업데이트
      setSelectedMedicine(result.data);
      setMedicineMetadata(result.meta);
      setActiveTab('info');
      setIsLoading(false);
    } catch (error) {
      console.error('의약품 상세 정보 가져오기 실패:', error);
      setError('의약품 정보를 가져오는 중 오류가 발생했습니다.');
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // 추출 완전성에 따른 색상 반환
  const getCompletenessColor = (completeness: number): string => {
    if (completeness >= 0.7) return 'bg-green-500';
    if (completeness >= 0.4) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  // 메타데이터 필드 렌더링
  const renderMetadataField = (label: string, value: any) => {
    return (
      <div className="mb-2">
        <div className="font-medium text-gray-700">{label}</div>
        <div className="bg-gray-50 p-2 rounded">
          {typeof value === 'boolean' ? (
            value ? (
              <CheckCircle className="text-green-500 inline-block" size={16} />
            ) : (
              <AlertCircle className="text-red-500 inline-block" size={16} />
            )
          ) : Array.isArray(value) ? (
            value.length > 0 ? (
              <ul className="list-disc pl-5">
                {value.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            ) : (
              <span className="text-gray-500">없음</span>
            )
          ) : (
            value || <span className="text-gray-500">없음</span>
          )}
        </div>
      </div>
    );
  };

  // 선택된 의약품 정보 렌더링
  const renderMedicineInfo = () => {
    if (!selectedMedicine || !medicineMetadata) return null;
    const medicine = selectedMedicine;

    // 카테고리별 필드 그룹화
    const basicFields = ['koreanName', 'englishName', 'category', 'company', 'appearance'];
    const detailFields = ['efficacy', 'dosage', 'precautions', 'sideEffects', 'interactions', 'storageMethod'];
    const specialGroupFields = ['pregnancyInfo', 'childrenInfo', 'elderlyInfo'];
    const identificationFields = ['drugCode', 'ingredients', 'formulation'];
    const otherFields = ['imageUrl', 'referenceUrls', 'lastUpdated'];

    // 필드 레이블 매핑
    const fieldLabels: Record<string, string> = {
      koreanName: '한글명',
      englishName: '영문명',
      category: '분류',
      company: '제조사',
      appearance: '성상',
      efficacy: '효능효과',
      dosage: '용법용량',
      precautions: '주의사항',
      sideEffects: '이상반응',
      interactions: '상호작용',
      storageMethod: '저장방법',
      pregnancyInfo: '임부 및 수유부',
      childrenInfo: '소아에 대한 투여',
      elderlyInfo: '고령자에 대한 투여',
      drugCode: '의약품 코드',
      ingredients: '성분',
      formulation: '제형',
      imageUrl: '이미지 URL',
      referenceUrls: '참고 URL',
      lastUpdated: '최종 업데이트'
    };

    // 특정 필드 그룹 렌더링 함수
    const renderFieldGroup = (fields: string[], title: string) => {
      const availableFields = fields.filter(field => {
        const value = medicine[field as keyof MedicineInfo];
        return value !== undefined && value !== null && value !== '';
      });
      
      if (availableFields.length === 0) return null;
      
      return (
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2 border-b pb-1">{title}</h3>
          {availableFields.map(field => {
            const value = medicine[field as keyof MedicineInfo];
            return (
              <div key={field} className="mb-4">
                <h4 className="font-medium text-gray-700 mb-1">{fieldLabels[field]}</h4>
                {Array.isArray(value) ? (
                  <ul className="list-disc pl-5">
                    {value.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                ) : field === 'imageUrl' && typeof value === 'string' ? (
                  <img 
                    src={value} 
                    alt={medicine.koreanName || '의약품 이미지'} 
                    className="mt-2 max-w-full h-auto border"
                  />
                ) : (
                  <p className="text-gray-800">{String(value)}</p>
                )}
              </div>
            );
          })}
        </div>
      );
    };

    // 정보 및 메타데이터 탭
    return (
      <div>
        <div className="mb-4 border-b">
          <div className="flex">
            <button
              className={`px-4 py-2 ${activeTab === 'info' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('info')}
            >
              의약품 정보
            </button>
            <button
              className={`px-4 py-2 ${activeTab === 'meta' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'}`}
              onClick={() => setActiveTab('meta')}
            >
              파싱 메타데이터
            </button>
          </div>
        </div>

        {activeTab === 'info' ? (
          <div>
            {medicine.koreanName && (
              <h3 className="text-xl font-bold mb-2">{medicine.koreanName}</h3>
            )}
            {medicine.englishName && (
              <p className="text-gray-600 mb-4">{medicine.englishName}</p>
            )}
            
            {renderFieldGroup(basicFields, '기본 정보')}
            {renderFieldGroup(detailFields, '상세 정보')}
            {renderFieldGroup(specialGroupFields, '특수 집단 정보')}
            {renderFieldGroup(identificationFields, '제품 식별 정보')}
            {renderFieldGroup(otherFields, '기타 정보')}
          </div>
        ) : (
          <div className="bg-gray-50 p-4 rounded">
            <h3 className="text-lg font-semibold mb-3">파싱 메타데이터</h3>
            
            {/* 추출 완전성 */}
            <div className="mb-4">
              <div className="font-medium text-gray-700 mb-1">추출 완전성</div>
              <div className="flex items-center">
                <div className="w-full bg-gray-200 rounded-full h-4 mr-2">
                  <div 
                    className={`${getCompletenessColor(medicineMetadata.completeness)} h-4 rounded-full`}
                    style={{ width: `${medicineMetadata.completeness * 100}%` }}
                  ></div>
                </div>
                <span className="whitespace-nowrap">
                  {(medicineMetadata.completeness * 100).toFixed(1)}%
                </span>
              </div>
            </div>
            
            {renderMetadataField('성공 여부', medicineMetadata.parsingSuccess)}
            {renderMetadataField('소스 URL', medicineMetadata.sourceUrl)}
            {renderMetadataField('추출된 필드', medicineMetadata.extractedFields)}
            {renderMetadataField('누락된 필드', medicineMetadata.missingFields)}
            
            {medicineMetadata.parsingErrors && medicineMetadata.parsingErrors.length > 0 && (
              renderMetadataField('파싱 오류', medicineMetadata.parsingErrors)
            )}
            
            <div className="mt-4 flex justify-end">
              <button
                className="flex items-center bg-blue-500 text-white px-3 py-2 rounded hover:bg-blue-600"
                onClick={() => {
                  const dataObj = {
                    data: selectedMedicine,
                    meta: medicineMetadata
                  };
                  const dataStr = JSON.stringify(dataObj, null, 2);
                  const dataUri = `data:text/json;charset=utf-8,${encodeURIComponent(dataStr)}`;
                  
                  const linkElement = document.createElement('a');
                  linkElement.setAttribute('href', dataUri);
                  linkElement.setAttribute('download', `${medicine.koreanName || 'medicine'}_data.json`);
                  document.body.appendChild(linkElement);
                  linkElement.click();
                  document.body.removeChild(linkElement);
                }}
              >
                <Download size={16} className="mr-1" /> JSON 다운로드
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-4">
      <div className="bg-white shadow-md rounded-lg p-4 mb-6">
        <h2 className="text-xl font-semibold mb-4">의약품 검색</h2>
        <div className="flex mb-4 relative">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onKeyPress={handleKeyPress}
            className="border rounded-l p-2 flex-grow focus:outline-none focus:ring-2 focus:ring-blue-300"
            placeholder="의약품 키워드 입력"
          />
          <button 
            onClick={handleSearch} 
            className="bg-blue-500 text-white px-4 py-2 rounded-r hover:bg-blue-600 flex items-center"
            disabled={isLoading}
          >
            {isLoading ? '검색 중...' : (
              <>
                <Search size={18} className="mr-1" /> 검색
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-100 text-red-700 rounded mb-4">
            {error}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 검색 결과 목록 */}
        <div className="bg-white shadow-md rounded-lg p-4">
          <h2 className="text-xl font-semibold mb-4">검색 결과</h2>
          {isLoading ? (
            <div className="flex justify-center items-center h-40">
              <div>로딩 중...</div>
            </div>
          ) : searchResults.length === 0 ? (
            <p className="text-gray-500">검색 결과가 없습니다. 키워드를 입력하고 검색해주세요.</p>
          ) : (
            searchResults.map((result, index) => (
              <div 
                key={index} 
                className="border rounded p-3 mb-3 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => fetchMedicineDetails(result.link, result.title)}
              >
                <h3 
                  className="font-medium text-blue-600 mb-1"
                  dangerouslySetInnerHTML={{ __html: result.title }} 
                />
                <p className="text-sm text-gray-600">{result.description}</p>
                <p className="text-xs text-gray-400 mt-1 truncate">{result.link}</p>
              </div>
            ))
          )}
        </div>

        {/* 선택된 의약품 상세 정보 */}
        <div className="bg-white shadow-md rounded-lg p-4">
          <h2 className="text-xl font-semibold mb-4">의약품 상세 정보</h2>
          {isLoading ? (
            <div className="flex justify-center items-center h-40">
              <div>정보를 불러오는 중...</div>
            </div>
          ) : selectedMedicine ? (
            renderMedicineInfo()
          ) : (
            <p className="text-gray-500">의약품을 선택하면 상세 정보가 표시됩니다.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default MedicineSearch;