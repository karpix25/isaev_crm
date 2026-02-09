import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/layout/Layout'
import { Dashboard } from './pages/Dashboard'
import { Leads } from './pages/Leads'
import { Chat } from './pages/Chat'
import { Projects } from './pages/Projects'
import { AISettings } from './pages/AISettings'
import { Login } from './pages/Login'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('access_token')
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

import { Toaster } from 'sonner'

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Toaster position="top-right" expand={true} richColors />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/" element={<PrivateRoute><Layout title="Бизнес-аналитика" /></PrivateRoute>}>
            <Route index element={<Dashboard />} />
          </Route>

          <Route path="/leads" element={<PrivateRoute><Layout title="Управление лидами" /></PrivateRoute>}>
            <Route index element={<Leads />} />
          </Route>

          <Route path="/projects" element={<PrivateRoute><Layout title="Проекты" /></PrivateRoute>}>
            <Route index element={<Projects />} />
          </Route>

          <Route path="/chat/:leadId?" element={<PrivateRoute><Layout title="AI Ассистент" /></PrivateRoute>}>
            <Route index element={<Chat />} />
          </Route>

          <Route path="/settings" element={<PrivateRoute><Layout title="Настройки системы" /></PrivateRoute>}>
            <Route index element={<AISettings />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
