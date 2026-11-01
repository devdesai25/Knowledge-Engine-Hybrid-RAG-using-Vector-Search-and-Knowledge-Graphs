import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Files } from 'lucide-react';

export const Documents: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col items-center justify-center text-center">
      <div className="max-w-md space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Files className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Documents Screen (Step 4)
        </h2>
        <p className="text-sm text-muted-foreground">
          Tenant document repository for <span className="font-semibold text-foreground">{user?.tenant.name}</span>.
        </p>
        <div className="rounded-lg border border-border bg-card p-4 text-xs text-muted-foreground">
          {isAdmin ? (
            <span className="text-amber-600 dark:text-amber-400 font-medium">
              Admin privileges verified: Multi-file drag-and-drop zone and deletion controls will be rendered here.
            </span>
          ) : (
            <span className="text-blue-600 dark:text-blue-400 font-medium">
              Member view verified: Read-only document table will be rendered here with no upload/delete actions.
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
