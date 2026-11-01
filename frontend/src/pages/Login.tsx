import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { isMockMode, SEEDED_USERS } from '@/api';
import { Button } from '@/components/ui/button';
import { Sparkles, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { switchUser } = useAuth();

  // Quick dev sign-in helper during Phase 1 scaffold
  const handleQuickSignIn = (seedKey: string) => {
    const seeded = SEEDED_USERS[seedKey];
    if (seeded) {
      switchUser(seeded, `mock-token-${seeded.id}`);
      toast.success(`Signed in as ${seeded.email}`);
      navigate('/chat');
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-6 rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="text-center space-y-2">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="h-5 w-5" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            Knowledge Engine
          </h1>
          <p className="text-xs text-muted-foreground">
            Hybrid RAG &bull; Phase 1 Scaffold Loaded
          </p>
        </div>

        {isMockMode && (
          <div className="space-y-3 rounded-lg bg-muted/50 p-4 border border-border/80">
            <p className="text-xs font-semibold text-foreground">
              Mock Mode Active &bull; Quick Seed Sign-In:
            </p>
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-between text-xs"
                onClick={() => handleQuickSignIn('tenant-a-admin')}
              >
                <span>Acme Corp &bull; Admin (admin@acme.com)</span>
                <ArrowRight className="h-3 w-3" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-between text-xs"
                onClick={() => handleQuickSignIn('tenant-a-member')}
              >
                <span>Acme Corp &bull; Member (member@acme.com)</span>
                <ArrowRight className="h-3 w-3" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-between text-xs"
                onClick={() => handleQuickSignIn('tenant-b-member')}
              >
                <span>Globex Corp &bull; Member (member@globex.com)</span>
                <ArrowRight className="h-3 w-3" />
              </Button>
            </div>
          </div>
        )}

        <div className="text-center text-xs text-muted-foreground">
          Step 1 (Scaffold + API layer + Mocks) is ready for review.
        </div>
      </div>
    </div>
  );
};
