import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { initTheme } from '@/lib/theme';
import { AppLayout } from '@/components/layout/AppLayout';
import { ProtectedRoute, AdminRoute } from '@/components/layout/ProtectedRoute';
import { Login } from '@/pages/Login';
import { Chat } from '@/pages/Chat';
import { Documents } from '@/pages/Documents';
import { Admin } from '@/pages/Admin';
import { NotFound } from '@/pages/NotFound';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 30, // 30 seconds
    },
  },
});

export const App: React.FC = () => {
  useEffect(() => {
    const cleanup = initTheme();
    return cleanup;
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          {/* Protected routes wrapped in AppLayout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/chat" replace />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/documents" element={<Documents />} />

              {/* Admin-only route: Members redirected to /chat */}
              <Route element={<AdminRoute />}>
                <Route path="/admin" element={<Admin />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  );
};

export default App;
