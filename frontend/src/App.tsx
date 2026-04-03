import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { AuthPage } from '@/pages/AuthPage'
import { ChatPage } from '@/pages/ChatPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { AdminSettingsPage } from '@/pages/AdminSettingsPage'
import { AuthGuard } from '@/components/auth/AuthGuard'
import { AdminGuard } from '@/components/auth/AdminGuard'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route
            path="/"
            element={
              <AuthGuard>
                <ChatPage />
              </AuthGuard>
            }
          />
          <Route
            path="/documents"
            element={
              <AuthGuard>
                <DocumentsPage />
              </AuthGuard>
            }
          />
          <Route
            path="/settings"
            element={
              <AuthGuard>
                <SettingsPage />
              </AuthGuard>
            }
          />
          <Route
            path="/admin/settings"
            element={
              <AuthGuard>
                <AdminGuard>
                  <AdminSettingsPage />
                </AdminGuard>
              </AuthGuard>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
