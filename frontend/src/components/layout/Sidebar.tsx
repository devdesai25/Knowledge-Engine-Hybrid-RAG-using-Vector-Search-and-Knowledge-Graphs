import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { MessageSquare, Files, ShieldAlert, Sparkles, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const navItems = [
    {
      label: 'Chat',
      to: '/chat',
      icon: MessageSquare,
      badge: 'RAG',
    },
    {
      label: 'Documents',
      to: '/documents',
      icon: Files,
    },
    // Admin tab is ONLY visible to admin role
    ...(isAdmin
      ? [
          {
            label: 'Admin',
            to: '/admin',
            icon: ShieldAlert,
            badge: 'Admin Only',
          },
        ]
      : []),
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-card/95 backdrop-blur transition-transform duration-200 ease-in-out md:static md:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand header */}
        <div className="flex h-14 items-center justify-between border-b border-border px-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-foreground">
                Knowledge Engine
              </h1>
              <p className="text-[10px] text-muted-foreground font-mono">
                Hybrid RAG &amp; Graph
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground md:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <div className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Workspace
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => onClose()}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground shadow-sm'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                    )
                  }
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-mono uppercase bg-background/20">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Bottom tenant identifier card */}
        <div className="border-t border-border p-3">
          <div className="rounded-lg bg-muted/60 p-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-foreground">
                {user?.tenant.name || 'Tenant'}
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">
                {user?.role}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground truncate">
              {user?.email}
            </p>
          </div>
        </div>
      </aside>
    </>
  );
};
