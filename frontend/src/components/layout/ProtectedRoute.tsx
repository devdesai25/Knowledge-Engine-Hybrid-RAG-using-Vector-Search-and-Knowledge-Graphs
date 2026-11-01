import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

export const ProtectedRoute: React.FC = () => {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};

export const AdminRoute: React.FC = () => {
  const { user } = useAuth();

  if (user?.role !== 'admin') {
    return <Navigate to="/chat" replace />;
  }

  return <Outlet />;
};
