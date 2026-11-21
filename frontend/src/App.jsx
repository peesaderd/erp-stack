import React from 'react';
import { BrowserRouter, Routes, Route, NavLink, Outlet } from 'react-router-dom';
import Header from './components/Header';
import Home from './pages/Home';
import MathPage from './pages/Math';
import Profile from './pages/Profile';
import Info from './pages/profile/Info';
import Settings from './pages/profile/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <Header />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/math/*" element={<MathPage />} />
        <Route path="/profile/*" element={<Profile />}> 
          <Route path="info" element={<Info />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
