import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import MedicineSearch from './components/MedicineSearch';
import MedicineDataViewer from './components/MedicineDataViewer';

function App() {
  return (
    <Router>
      <div className="container mx-auto p-4">
        <header className="bg-white shadow-md rounded-lg mb-6">
          <div className="p-4">
            <h1 className="text-2xl font-bold text-center">의약품 정보 시스템</h1>
            <nav className="flex justify-center mt-4">
              <Link to="/" className="mx-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
                의약품 검색
              </Link>
              <Link to="/data-viewer" className="mx-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
                데이터 검증
              </Link>
            </nav>
          </div>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<MedicineSearch />} />
            <Route path="/data-viewer" element={<MedicineDataViewer />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;