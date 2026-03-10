/**
 * Main Application Component (App.jsx)
 * ====================================
 * 
 * This is the root component of the React frontend application for the Timetable System.
 * It is responsible for:
 * 1. Setting up the Global Application State Providers (Theme, Auth, Google OAuth)
 * 2. Defining the Navigation Layout (Sidebar, Topbar)
 * 3. Handling Client-Side Routing (React Router)
 * 4. Enforcing Role-Based Access Control (RBAC) on routes via ProtectedRoute.
 * 
 * Author: Frontend Team (Bhuvanesh, Akshitha)
 * Sprint: 1
 */

// Import React Router components for handling navigation without reloading the page
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';

// Import global CSS styles
import './index.css';

// ==========================================
// IMPORT ALL PAGE COMPONENTS
// ==========================================
import Dashboard from './pages/Dashboard';
import DataManagement from './pages/DataManagement';
import GenerateSchedule from './pages/GenerateSchedule';
import ViewTimetable from './pages/ViewTimetable';
import Analytics from './pages/Analytics';
import AuditLogs from './pages/AuditLogs';
import UserManagement from './pages/UserManagement';
import ChangeRequests from './pages/ChangeRequests';
import TeacherRequests from './pages/TeacherRequests';
import SystemHealth from './pages/SystemHealth';
import Login from './pages/Login';
import FacultyMapping from './pages/FacultyMapping';

// ==========================================
// IMPORT CONTEXT PROVIDERS & HOCs
// ==========================================
import { AuthProvider, useAuth } from './context/AuthContext';       // Manages user login state
import { ThemeProvider, useTheme } from './context/ThemeContext';     // Manages Light/Dark mode
import { GoogleOAuthProvider } from '@react-oauth/google';            // Wraps app for Google Sign-In
import ProtectedRoute from './components/ProtectedRoute';               // Higher-Order Component to block unauthorized users
import NotificationBell from './components/NotificationBell';           // UI component for alerts

// Read Google Client ID from environment variables (.env file).
// Fallback provided just in case the env var is missing during dev.
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "PASTE_YOUR_REAL_ID_HERE.apps.googleusercontent.com";


/**
 * MainLayout Component
 * --------------------
 * Acts as a wrapper around the main content of authenticated pages.
 * It provides the sticky Sidebar navigation on the left and the Topbar header.
 * 
 * @param {object} props - Contains `children` which is the specific Page component being rendered.
 */
const MainLayout = ({ children }) => {
  // Extract user data and logout function from the global AuthContext
  const { user, logout } = useAuth();

  // Extract current theme state and theme toggler from the global ThemeContext
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="app-container">
      {/* 
        ==============================
        SIDEBAR NAVIGATION 
        ==============================
      */}
      <aside className="sidebar">
        {/* App Logo/Header */}
        <div className="sidebar-header">
          <h1 className="sidebar-title">M3</h1>
          <p className="sidebar-subtitle">Timetable System</p>
        </div>

        <nav>
          <ul className="nav-menu">
            {/* Common Item: Dashboard is visible to everyone */}
            <li className="nav-item">
              <Link to="/dashboard" className="nav-link">
                Dashboard
              </Link>
            </li>

            {/* 
              ADMIN SPECIFIC LINKS 
              Only render these navigation links if the logged-in user's role is exactly 'ADMIN'
            */}
            {user?.role === 'ADMIN' && (
              <>
                <li className="nav-item">
                  <Link to="/data" className="nav-link">
                    Data Management
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/generate" className="nav-link">
                    Generate Schedule
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/timetable" className="nav-link">
                    View Timetable
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/analytics" className="nav-link">
                    Analytics
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/users" className="nav-link">
                    Users
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/change-requests" className="nav-link">
                    Change Requests
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/audit-logs" className="nav-link">
                    Audit Logs
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/system-health" className="nav-link">
                    System Health
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/faculty-mapping" className="nav-link">
                    Faculty Mapping
                  </Link>
                </li>
              </>
            )}

            {/* 
              HOD (Head of Dept) SPECIFIC LINKS 
              Visible only to HODs. They can approve teacher requests and see analytics.
            */}
            {user?.role === 'HOD' && (
              <>
                <li className="nav-item">
                  <Link to="/teacher-requests" className="nav-link">
                    Faculty Management
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/timetable" className="nav-link">
                    View Timetable
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/analytics" className="nav-link">
                    Analytics
                  </Link>
                </li>
                <li className="nav-item">
                  <Link to="/faculty-mapping" className="nav-link">
                    Faculty Mapping
                  </Link>
                </li>
              </>
            )}

            {/* 
              FACULTY SPECIFIC LINKS 
              Standard teachers can only view schedules.
            */}
            {user?.role === 'FACULTY' && (
              <li className="nav-item">
                <Link to="/timetable" className="nav-link">
                  View Timetable
                </Link>
              </li>
            )}

            {/* 
              LOGOUT BUTTON 
              Pushed to the very bottom of the sidebar using `marginTop: auto` 
              (assuming flexbox column on nav-menu)
            */}
            <li className="nav-item" style={{ marginTop: 'auto' }}>
              <button
                onClick={logout}
                className="nav-link"
                style={{
                  width: '100%',
                  textAlign: 'left',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--danger)', // Uses CSS variable for red color
                  marginTop: '2rem'
                }}
              >
                Logout
              </button>
            </li>
          </ul>
        </nav>
      </aside>

      {/* 
        ==============================
        MAIN CONTENT AREA 
        ==============================
        This section takes up the remaining screen space to the right of the sidebar.
      */}
      <main className="main-content">

        {/* Top Header Bar spanning the width of the main content window */}
        <header className="top-bar">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '12px' }}>

            {/* Display the active user's name and role */}
            <div className="user-welcome" style={{ marginRight: '4px' }}>
              Welcome, {user?.first_name || user?.username} ({user?.role})
            </div>

            {/* Component showing unread alerts */}
            <NotificationBell />

            {/* Theme Toggle Switch (Dark/Light mode) */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                {theme === 'light' ? 'Light' : 'Dark'}
              </span>
              <label className="theme-switch">
                <input
                  type="checkbox"
                  checked={theme === 'dark'}
                  onChange={toggleTheme}
                />
                <span className="slider">
                  <span className="icon">☀️</span>
                  <span className="icon">🌙</span>
                </span>
              </label>
            </div>
          </div>
        </header>

        {/* 
          The actual page content (Dashboard, ViewTimetable, etc.) is injected here.
          The 'fade-in' class applies a CSS animation when switching pages.
        */}
        <div className="fade-in">
          {children}
        </div>
      </main>
    </div>
  );
};

/**
 * App (Root Component)
 * -------------------
 * Sets up the React Context tree and defines the Routing table.
 */
function App() {
  return (
    // <Router> enables the HTML5 History API for seamless client-side routing
    <Router>
      {/* <ThemeProvider> supplies Light/Dark mode state to the whole app */}
      <ThemeProvider>
        {/* <GoogleOAuthProvider> injects Google Auth JS scripts to enable Sign In With Google */}
        <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
          {/* <AuthProvider> manages the JWT token and User session state */}
          <AuthProvider>

            {/* <Routes> acts like a switch statement, rendering only the First matching Route */}
            <Routes>

              {/* Public Unprotected Route: Login Page */}
              <Route path="/login" element={<Login />} />

              {/* 
                ==============================
                PROTECTED ROUTES 
                ==============================
                These routes require the user to be logged in. 
                If not, <ProtectedRoute> will intercept and redirect to /login.
              */}

              {/* Root URL redirects to dashboard */}
              <Route path="/" element={
                <ProtectedRoute>
                  <Navigate to="/dashboard" replace />
                </ProtectedRoute>
              } />

              {/* Dashboard is a protected route available to ALL roles. */}
              <Route path="/dashboard" element={
                <ProtectedRoute>
                  <MainLayout><Dashboard /></MainLayout>
                </ProtectedRoute>
              } />

              {/* Data Management: Strictly ADMIN only. */}
              <Route path="/data" element={
                <ProtectedRoute roles={['ADMIN']}>
                  <MainLayout><DataManagement /></MainLayout>
                </ProtectedRoute>
              } />

              {/* Generate Schedule Engine: Strictly ADMIN only. */}
              <Route path="/generate" element={
                <ProtectedRoute roles={['ADMIN']}>
                  <MainLayout><GenerateSchedule /></MainLayout>
                </ProtectedRoute>
              } />

              {/* View Timetable: Shared feature accessible by everyone */}
              <Route path="/timetable" element={
                <ProtectedRoute>
                  <MainLayout><ViewTimetable /></MainLayout>
                </ProtectedRoute>
              } />

              {/* Analytics: Only Admins and HODs (Department Heads) can view metrics */}
              <Route path="/analytics" element={
                <ProtectedRoute roles={['ADMIN', 'HOD']}>
                  <MainLayout><Analytics /></MainLayout>
                </ProtectedRoute>
              } />

              {/* System Admin Settings (Users, Audits, Health) */}
              <Route path="/users" element={
                <ProtectedRoute roles={['ADMIN']}>
                  <MainLayout><UserManagement /></MainLayout>
                </ProtectedRoute>
              } />

              <Route path="/change-requests" element={
                <ProtectedRoute roles={['ADMIN']}>
                  <MainLayout><ChangeRequests /></MainLayout>
                </ProtectedRoute>
              } />

              <Route path="/teacher-requests" element={
                <ProtectedRoute roles={['HOD']}>
                  <MainLayout><TeacherRequests /></MainLayout>
                </ProtectedRoute>
              } />

              <Route path="/audit-logs" element={
                <ProtectedRoute roles={['ADMIN']}>
                  <MainLayout><AuditLogs /></MainLayout>
                </ProtectedRoute>
              } />

              <Route path="/system-health" element={
                <ProtectedRoute roles={['ADMIN']}>
                  <MainLayout><SystemHealth /></MainLayout>
                </ProtectedRoute>
              } />

              {/* Faculty Mapping: Admin + HOD can access */}
              <Route path="/faculty-mapping" element={
                <ProtectedRoute roles={['ADMIN', 'HOD']}>
                  <MainLayout><FacultyMapping /></MainLayout>
                </ProtectedRoute>
              } />

              {/* 
                CATCH-ALL ROUTE (404 Fallback)
                If user types a random URL like /blahblah, intercept it.
                If logged in, send to Dashboard.
                If not logged in, ProtectedRoute (within Dashboard) will eventually send them to Login.
              */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />

            </Routes>
          </AuthProvider>
        </GoogleOAuthProvider>
      </ThemeProvider>
    </Router>
  );
}

export default App;
