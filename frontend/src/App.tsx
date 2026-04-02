import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthPage } from '@/pages/AuthPage'
import { ChatPage } from '@/pages/ChatPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { AuthGuard } from '@/components/auth/AuthGuard'

export default function App() {
  return (
    <BrowserRouter>
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
