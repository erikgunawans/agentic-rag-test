import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { I18nProvider } from '@/i18n/I18nContext'
import { AuthPage } from '@/pages/AuthPage'
import { ChatPage } from '@/pages/ChatPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { AdminSettingsPage } from '@/pages/AdminSettingsPage'
import { DocumentCreationPage } from '@/pages/DocumentCreationPage'
import { DocumentComparisonPage } from '@/pages/DocumentComparisonPage'
import { ComplianceCheckPage } from '@/pages/ComplianceCheckPage'
import { ContractAnalysisPage } from '@/pages/ContractAnalysisPage'
import { AuditTrailPage } from '@/pages/AuditTrailPage'
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { ObligationsPage } from '@/pages/ObligationsPage'
import { AuthGuard } from '@/components/auth/AuthGuard'
import { AdminGuard } from '@/components/auth/AdminGuard'
import { AppLayout } from '@/layouts/AppLayout'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <I18nProvider>
          <Routes>
            <Route path="/auth" element={<AuthPage />} />
            <Route
              path="/"
              element={
                <AuthGuard>
                  <AppLayout />
                </AuthGuard>
              }
            >
              <Route index element={<ChatPage />} />
              <Route path="documents" element={<DocumentsPage />} />
              <Route path="create" element={<DocumentCreationPage />} />
              <Route path="compare" element={<DocumentComparisonPage />} />
              <Route path="compliance" element={<ComplianceCheckPage />} />
              <Route path="analysis" element={<ContractAnalysisPage />} />
              <Route path="obligations" element={<ObligationsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route
                path="admin/settings"
                element={
                  <AdminGuard>
                    <AdminSettingsPage />
                  </AdminGuard>
                }
              />
              <Route
                path="admin/audit"
                element={
                  <AdminGuard>
                    <AuditTrailPage />
                  </AdminGuard>
                }
              />
              <Route
                path="admin/reviews"
                element={
                  <AdminGuard>
                    <ReviewQueuePage />
                  </AdminGuard>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </I18nProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
