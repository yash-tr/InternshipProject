import React, { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { toggleBanner } from './store/slices/uiSlice';
import { fetchUserData } from './store/slices/userSlice';
import { useEffect } from 'react';

// Lazy loading components for code splitting
const ResumeBuilder = lazy(() => import('./components/ResumeBuilder'));
const EventPage = lazy(() => import('./components/EventPage'));
const Dashboard = lazy(() => import('./components/Dashboard'));

// Components
import Navbar from './components/Navbar';
import ConditionalModal from './components/ConditionalModal';
import DiwaliBanner from './components/DiwaliBanner';
import LoadingSpinner from './components/LoadingSpinner';

function App() {
  const dispatch = useDispatch();
  const { showBanner, bannerType } = useSelector(state => state.ui);
  const { user, loading } = useSelector(state => state.user);

  useEffect(() => {
    // Fetch user data on app load
    dispatch(fetchUserData());
  }, [dispatch]);

  const handleBannerToggle = () => {
    dispatch(toggleBanner());
  };

  return (
    <div className="App">
      <Navbar />
      
      {/* Diwali Banner - conditionally rendered */}
      {showBanner && <DiwaliBanner onClose={handleBannerToggle} />}
      
      <div className="container">
        <Routes>
          <Route path="/" element={
            <Suspense fallback={<LoadingSpinner />}>
              <Dashboard />
            </Suspense>
          } />
          <Route path="/resume-builder" element={
            <Suspense fallback={<LoadingSpinner />}>
              <ResumeBuilder />
            </Suspense>
          } />
          <Route path="/event" element={
            <Suspense fallback={<LoadingSpinner />}>
              <EventPage />
            </Suspense>
          } />
        </Routes>
      </div>

      {/* Conditional Modal - can be triggered from any component */}
      <ConditionalModal />
    </div>
  );
}

export default App;
