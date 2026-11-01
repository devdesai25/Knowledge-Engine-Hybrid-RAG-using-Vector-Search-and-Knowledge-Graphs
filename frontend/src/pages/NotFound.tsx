import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';

export const NotFound: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 text-center">
      <h1 className="text-4xl font-extrabold tracking-tight">404</h1>
      <p className="mt-2 text-sm text-muted-foreground">The page you are looking for does not exist.</p>
      <div className="mt-4">
        <Link to="/chat">
          <Button variant="default" size="sm">
            Go to Chat
          </Button>
        </Link>
      </div>
    </div>
  );
};
