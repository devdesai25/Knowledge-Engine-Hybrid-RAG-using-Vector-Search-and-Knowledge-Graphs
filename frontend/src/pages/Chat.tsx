import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Badge } from '@/components/ui/badge';
import { MessageSquare } from 'lucide-react';

export const Chat: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col items-center justify-center text-center">
      <div className="max-w-md space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <MessageSquare className="h-6 w-6" />
        </div>
        <h2 className="text-xl font-bold tracking-tight text-foreground">
          Chat Screen (Step 3)
        </h2>
        <p className="text-sm text-muted-foreground">
          Current tenant: <span className="font-semibold text-foreground">{user?.tenant.name}</span>.
          Streaming SSE Q&amp;A with citations side panel will be built in Step 3.
        </p>
        <div className="flex justify-center gap-2">
          <Badge variant="outline" className="text-xs">
            User: {user?.email}
          </Badge>
          <Badge variant="outline" className="text-xs uppercase">
            Role: {user?.role}
          </Badge>
        </div>
      </div>
    </div>
  );
};
