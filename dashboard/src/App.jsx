import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getToken } from './api';
import Login from './pages/Login';
import Clients from './pages/Clients';
import ClientDetail from './pages/ClientDetail';

function PrivateRoute({ children }) {
  return getToken() ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><Clients /></PrivateRoute>} />
        <Route path="/clients/:clientId" element={<PrivateRoute><ClientDetail /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
