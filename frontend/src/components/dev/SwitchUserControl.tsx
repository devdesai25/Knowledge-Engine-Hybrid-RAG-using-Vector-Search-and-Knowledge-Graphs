import React, { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { SEEDED_USERS, mockStore, isMockMode } from '@/api';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { UserCheck, Shield, Users, Building, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react';

export const SwitchUserControl: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { user, switchUser } = useAuth();
  const queryClient = useQueryClient();

  if (!isMockMode) {
    return null;
  }

  const handleSelectUser = (seedKey: string) => {
    const targetUser = SEEDED_USERS[seedKey];
    if (!targetUser) return;

    switchUser(targetUser, `mock-token-${targetUser.id}`);
    queryClient.invalidateQueries();
    toast.success(`Switched to ${targetUser.email} (${targetUser.role})`, {
      description: `Tenant: ${targetUser.tenant.name}`,
    });
    setIsOpen(false);
  };

  const handleResetData = () => {
    mockStore.resetToDefaults();
    queryClient.invalidateQueries();
    toast.info('Mock database reset to initial seeded data.');
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 font-sans">
      {isOpen ? (
        <div className="w-80 rounded-xl border border-border bg-card p-4 shadow-2xl backdrop-blur-md transition-all animate-in fade-in slide-in-from-bottom-2">
          <div className="flex items-center justify-between pb-3 border-b border-border">
            <div className="flex items-center gap-2">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Dev Persona Switcher
              </span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-muted-foreground hover:text-foreground text-xs p-1 rounded hover:bg-muted"
            >
              <ChevronDown className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-3 space-y-2">
            {Object.entries(SEEDED_USERS).map(([key, seededUser]) => {
              const isActive = user?.email === seededUser.email;
              const isAdmin = seededUser.role === 'admin';

              return (
                <button
                  key={key}
                  onClick={() => handleSelectUser(key)}
                  className={`w-full text-left p-2.5 rounded-lg border transition-all text-sm flex items-center justify-between ${
                    isActive
                      ? 'border-primary bg-primary/10 font-medium text-foreground ring-1 ring-primary'
                      : 'border-border/60 hover:border-border hover:bg-muted/50 text-muted-foreground'
                  }`}
                >
                  <div className="min-w-0 pr-2">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold text-foreground truncate text-xs">
                        {seededUser.tenant.name}
                      </span>
                      <span
                        className={`text-[10px] px-1.5 py-0.2 rounded font-mono uppercase font-bold ${
                          isAdmin
                            ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                            : 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                        }`}
                      >
                        {seededUser.role}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">
                      {seededUser.email}
                    </p>
                  </div>
                  {isActive && <UserCheck className="h-4 w-4 text-primary shrink-0" />}
                </button>
              );
            })}
          </div>

          <div className="mt-3 pt-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
            <span className="text-[11px]">Mock Mode: Active</span>
            <button
              onClick={handleResetData}
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground hover:underline p-1"
              title="Reset mock documents and members"
            >
              <RotateCcw className="h-3 w-3" />
              Reset State
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setIsOpen(true)}
          className="group flex items-center gap-2.5 rounded-full border border-border bg-card/95 px-3.5 py-2 shadow-lg backdrop-blur hover:bg-muted/80 hover:shadow-xl transition-all"
        >
          <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
            <Building className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="max-w-[100px] truncate">{user?.tenant.name || 'Mock Tenant'}</span>
            <span className="text-muted-foreground">/</span>
            {user?.role === 'admin' ? (
              <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400 font-semibold">
                <Shield className="h-3 w-3" /> Admin
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400">
                <Users className="h-3 w-3" /> Member
              </span>
            )}
          </div>
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground group-hover:text-foreground" />
        </button>
      )}
    </div>
  );
};
