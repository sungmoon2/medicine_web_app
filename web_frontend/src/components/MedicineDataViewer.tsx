import React, { useState, useEffect } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';

// 의약품 인터페이스 정의
interface Medicine {
  id: number;
  korean_name: string;
  english_name: string;
  url: string;
  category: string;
  company: string;
}

interface MedicineDetails {
  database_details: any;
  original_url: string;
  html_preview?: string;
}

interface ValidationResult {
  details: any;
  validation: Record<string, boolean>;
  extraction_completeness: number;
}

const MedicineDataViewer: React.FC = () => {
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [selectedMedicine, setSelectedMedicine] = useState<MedicineDetails | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 의약품 목록 로드
  useEffect(() => {
    const fetchMedicines = async () => {
      try {
        setIsLoading(true);
        const response = await fetch('/api/medicines');
        const data = await response.json();
        setMedicines(data.medicines);
        setIsLoading(false);
      } catch (error) {
        console.error('의약품 목록 로드 실패:', error);
        setError('의약품 목록을 불러오는 데 실패했습니다.');
        setIsLoading(false);
      }
    };

    fetchMedicines();
  }, []);

  // 의약품 상세 정보 및 검증 로드
  const loadMedicineDetails = async (url: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // 상세 정보 로드
      const detailsResponse = await fetch(`/api/medicine/url?url=${encodeURIComponent(url)}`);
      const details = await detailsResponse.json();
      setSelectedMedicine(details);

      // 데이터 검증
      const validationResponse = await fetch(`/api/medicine/validate-extraction/${encodeURIComponent(url)}`);
      const validation = await validationResponse.json();
      setValidationResult(validation);
      
      setIsLoading(false);
      setIsModalOpen(true);
    } catch (error) {
      console.error('의약품 상세 정보 로드 실패:', error);
      setError('의약품 상세 정보를 불러오는 데 실패했습니다.');
      setIsLoading(false);
    }
  };

  // 검증 결과 렌더링 헬퍼
  const renderValidationStatus = (field: string) => {
    if (!validationResult) return null;
    
    const isValid = validationResult.validation[field];
    return isValid ? (
      <CheckCircle2 className="text-green-500 inline-block" size={20} />
    ) : (
      <XCircle className="text-red-500 inline-block" size={20} />
    );
  };

  // 로딩 상태 렌더링
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div>로딩 중...</div>
      </div>
    );
  }

  // 에러 상태 렌더링
  if (error) {
    return (
      <div className="p-4 bg-red-100 text-red-800">
        {error}
      </div>
    );
  }

  return (
    <div className="p-4 max-w-full">
      <div className="bg-white shadow-md rounded-lg">
        <div className="p-4 border-b">
          <h2 className="text-xl font-semibold">수집된 의약품 데이터 검토</h2>
        </div>
        <div className="p-4">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-100">
                <th className="border p-2">ID</th>
                <th className="border p-2">한글명</th>
                <th className="border p-2">영문명</th>
                <th className="border p-2">분류</th>
                <th className="border p-2">제약회사</th>
                <th className="border p-2">상세 정보</th>
              </tr>
            </thead>
            <tbody>
              {medicines.map((medicine) => (
                <tr key={medicine.id} className="hover:bg-gray-50">
                  <td className="border p-2 text-center">{medicine.id}</td>
                  <td className="border p-2">{medicine.korean_name}</td>
                  <td className="border p-2">{medicine.english_name}</td>
                  <td className="border p-2">{medicine.category}</td>
                  <td className="border p-2">{medicine.company}</td>
                  <td className="border p-2 text-center">
                    <button 
                      onClick={() => loadMedicineDetails(medicine.url)}
                      className="bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600"
                    >
                      상세 보기
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 모달 */}
      {isModalOpen && selectedMedicine && validationResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
          <div className="bg-white p-6 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">{selectedMedicine.database_details.korean_name} 상세 정보</h2>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="text-gray-600 hover:text-gray-900"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* 데이터베이스 상세 정보 */}
              <div>
                <h3 className="text-lg font-semibold mb-2">데이터베이스 정보</h3>
                <table className="w-full border-collapse">
                  <tbody>
                    {Object.entries(validationResult.details).map(([key, value]) => (
                      <tr key={key} className="border-b">
                        <td className="p-2 font-medium">{key}</td>
                        <td className="p-2">
                          {typeof value === 'string' ? value : JSON.stringify(value)}
                        </td>
                        <td className="p-2">{renderValidationStatus(key)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {/* 원본 URL 미리보기 */}
              <div>
                <h3 className="text-lg font-semibold mb-2">원본 URL 미리보기</h3>
                <div className="border p-2 max-h-96 overflow-auto">
                  <a 
                    href={selectedMedicine.original_url} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    원본 URL 바로가기
                  </a>
                  {selectedMedicine.html_preview && (
                    <pre className="text-xs mt-2 bg-gray-100 p-2 rounded">
                      {selectedMedicine.html_preview}
                    </pre>
                  )}
                </div>
              </div>
            </div>
            
            {/* 추출 완전성 */}
            <div className="mt-4">
              <h3 className="text-lg font-semibold">데이터 추출 완전성</h3>
              <div className="flex items-center">
                <div className="w-full bg-gray-200 rounded-full h-4 mr-2">
                  <div 
                    className="bg-blue-600 h-4 rounded-full" 
                    style={{
                      width: `${(validationResult.extraction_completeness * 100).toFixed(2)}%`
                    }}
                  ></div>
                </div>
                <span>
                  {(validationResult.extraction_completeness * 100).toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MedicineDataViewer;