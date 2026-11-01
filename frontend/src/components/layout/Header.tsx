import React, { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { storage } from '@/lib/storage';
import { applyTheme, ThemeMode } from '@/lib/theme';
import {
  Building2,
  LogOut,
  Sun,
  Moon,
  Laptop,
  Menu,
  ChevronDown,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface HeaderProps {
  onToggleSidebar: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const { user, logout } = useAuth();
  const [themeMode, setThemeMode] = useState<ThemeMode>(storage.getTheme());
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const cycleTheme = () => {
    const nextTheme: ThemeMode =
      themeMode === 'system' ? 'light' : themeMode === 'light' ? 'dark' : 'system';
    setThemeMode(nextTheme);
    storage.setTheme(nextTheme);
    applyTheme(nextTheme);
  };

  const getThemeIcon = () => {
    if (themeMode === 'light') return <Sun className="h-4 w-4 text-amber-500" />;
    if (themeMode === 'dark') return <Moon className="h-4 w-4 text-blue-400" />;
    return <Laptop className="h-4 w-4 text-muted-foreground" />;
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="inline-flex items-center justify-center rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground md:hidden"
          aria-label="Toggle navigation"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Tenant name display */}
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Building2 className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold tracking-tight text-foreground">
                {user?.tenant.name || 'Organization'}
              </span>
              <span className="hidden text-[10px] text-muted-foreground sm:inline-block font-mono bg-muted px-1.5 py-0.5 rounded">
                Tenant: {user?.tenant.id || 'default'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Theme mode toggle */}
        <button
          onClick={cycleTheme}
          className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-background hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
          title={`Theme: ${themeMode} (click to cycle)`}
          aria-label="Toggle color theme"
        >
          {getThemeIcon()}
        </button>

        {/* User profile dropdown / info */}
        <div className="relative">
          <button
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className="flex items-center gap-2 rounded-lg border border-border/80 px-2.5 py-1 text-xs hover:bg-accent transition-colors"
          >
            <div className="flex flex-col text-left">
              <span className="font-medium text-foreground max-w-[140px] truncate sm:max-w-[200px]">
                {user?.email || 'User'}
              </span>
            </div>
            <Badge
              variant={user?.role === 'admin' ? 'warning' : 'info'}
              className="text-[10px] uppercase font-bold py-0 px-1.5"
            >
              {user?.role || 'member'}
            </Badge>
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </button>

          {isUserMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setIsUserMenuOpen(false)}
              />
              <div className="absolute right-0 mt-2 w-56 rounded-md border border-border bg-popover p-1.5 shadow-lg z-50 animate-in fade-in zoom-in-95">
                <div className="px-2 py-1.5 border-b border-border mb-1">
                  <p className="text-xs font-semibold text-foreground truncate">{user?.email}</p>
                  <p className="text-[11px] text-muted-foreground capitalize">
                    Role: {user?.role} • {user?.tenant.name}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
