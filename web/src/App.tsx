import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import ProfilesPage from './pages/ProfilesPage'
import ProfileFormPage from './pages/ProfileFormPage'
import JobsPage from './pages/JobsPage'
import JobDetailPage from './pages/JobDetailPage'
import AddJobPage from './pages/AddJobPage'
import TopJobsPage from './pages/TopJobsPage'
import DocumentsPage from './pages/DocumentsPage'
import AdminDashboard from './pages/admin/AdminDashboard'
import AdminJobsPage from './pages/admin/AdminJobsPage'
import AdminScraperPage from './pages/admin/AdminScraperPage'
import AdminPipelinePage from './pages/admin/AdminPipelinePage'
import NotFoundPage from './pages/NotFoundPage'

// Protected route component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }
  
  if (!user) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}

// Admin route component
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }
  
  if (!user || !user.is_admin) {
    return <Navigate to="/" replace />
  }
  
  return <>{children}</>
}

function AppRoutes() {
  const { user } = useAuth()
  
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/register" element={user ? <Navigate to="/" replace /> : <RegisterPage />} />
      
      {/* Protected routes */}
      <Route path="/" element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }>
        <Route index element={<DashboardPage />} />
        
        {/* Profile routes */}
        <Route path="profiles" element={<ProfilesPage />} />
        <Route path="profiles/new" element={<ProfileFormPage />} />
        <Route path="profiles/:id" element={<ProfileFormPage />} />
        
        {/* Job routes */}
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/add" element={<AddJobPage />} />
        <Route path="jobs/top" element={<TopJobsPage />} />
        <Route path="jobs/:id" element={<JobDetailPage />} />
        
        {/* Document routes */}
        <Route path="documents" element={<DocumentsPage />} />
        
        {/* Admin routes */}
        <Route path="admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
        <Route path="admin/jobs" element={<AdminRoute><AdminJobsPage /></AdminRoute>} />
        <Route path="admin/scraper" element={<AdminRoute><AdminScraperPage /></AdminRoute>} />
        <Route path="admin/pipeline" element={<AdminRoute><AdminPipelinePage /></AdminRoute>} />

        {/* 404 catch-all */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
