import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import { ShieldCheck } from 'lucide-react';

export const Admin: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col items-center justify-center text-center">
      <div className="max-w-md space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600">
          <ShieldCheck className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Tenant Administration (Step 5)
        </h2>
        <p className="text-sm text-muted-foreground">
          User management &amp; member invite workspace for <span className="font-semibold text-foreground">{user?.tenant.name}</span>.
        </p>
        <p className="text-xs text-muted-foreground">
          Protected by AdminRoute. Members attempting to access this route are automatically redirected to /chat.
        </p>
      </div>
    </div>
  );
};
