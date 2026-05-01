import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { ThemeProvider } from '@/theme/ThemeContext'
import { I18nProvider } from '@/i18n/I18nContext'
import { AuthPage } from '@/pages/AuthPage'
import { ChatPage } from '@/pages/ChatPage'
import { DocumentsPage } from '@/pages/DocumentsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SkillsPage } from '@/pages/SkillsPage'
import { AdminSettingsPage } from '@/pages/AdminSettingsPage'
import { DocumentCreationPage } from '@/pages/DocumentCreationPage'
import { DocumentComparisonPage } from '@/pages/DocumentComparisonPage'
import { ComplianceCheckPage } from '@/pages/ComplianceCheckPage'
import { ContractAnalysisPage } from '@/pages/ContractAnalysisPage'
import { AuditTrailPage } from '@/pages/AuditTrailPage'
import { ReviewQueuePage } from '@/pages/ReviewQueuePage'
import { ObligationsPage } from '@/pages/ObligationsPage'
import { ClauseLibraryPage } from '@/pages/ClauseLibraryPage'
import { ApprovalInboxPage } from '@/pages/ApprovalInboxPage'
import { RegulatoryPage } from '@/pages/RegulatoryPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { IntegrationsPage } from '@/pages/IntegrationsPage'
import { UserManagementPage } from '@/pages/UserManagementPage'
import { BJRDashboardPage } from '@/pages/BJRDashboardPage'
import { BJRDecisionPage } from '@/pages/BJRDecisionPage'
import { ComplianceTimelinePage } from '@/pages/ComplianceTimelinePage'
import { PDPDashboardPage } from '@/pages/PDPDashboardPage'
import { DataInventoryPage } from '@/pages/DataInventoryPage'
import { DataBreachPage } from '@/pages/DataBreachPage'
import { AuthGuard } from '@/components/auth/AuthGuard'
import { AdminGuard } from '@/components/auth/AdminGuard'
import { AppLayout } from '@/layouts/AppLayout'
import { TooltipProvider } from '@/components/ui/tooltip'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ThemeProvider>
        <I18nProvider>
          <TooltipProvider delay={300}>
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
              <Route path="clause-library" element={<ClauseLibraryPage />} />
              <Route path="skills" element={<SkillsPage />} />
              <Route path="compare" element={<DocumentComparisonPage />} />
              <Route path="compliance" element={<ComplianceCheckPage />} />
              <Route path="compliance/timeline" element={<ComplianceTimelinePage />} />
              <Route path="pdp" element={<PDPDashboardPage />} />
              <Route path="pdp/inventory" element={<DataInventoryPage />} />
              <Route path="pdp/incidents" element={<DataBreachPage />} />
              <Route path="analysis" element={<ContractAnalysisPage />} />
              <Route path="obligations" element={<ObligationsPage />} />
              <Route path="approvals" element={<ApprovalInboxPage />} />
              <Route path="regulatory" element={<RegulatoryPage />} />
              <Route path="bjr" element={<BJRDashboardPage />} />
              <Route path="bjr/decisions/:id" element={<BJRDecisionPage />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="integrations" element={<IntegrationsPage />} />
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
                path="admin/users"
                element={
                  <AdminGuard>
                    <UserManagementPage />
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
          </TooltipProvider>
        </I18nProvider>
        </ThemeProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
