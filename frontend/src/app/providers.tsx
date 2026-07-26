"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useEffect, useState } from "react";

import { onTokenChange } from "@/lib/api";
import { realtime } from "@/lib/ws";
import { useSession } from "@/stores/session";
import { storedTheme, useUi } from "@/stores/ui";

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // The WebSocket pushes changes, so aggressive refetching would duplicate
        // work the socket already does. Data is trusted until an event says
        // otherwise; the window focus refetch is the safety net for a missed frame.
        staleTime: 30_000,
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => {
          // Never retry an authorisation failure — the answer will not change,
          // and retrying a 401 races the token refresh.
          const status = (error as { status?: number }).status;
          if (status === 401 || status === 403 || status === 404) return false;
          return failureCount < 2;
        },
      },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  // Created in state, not at module scope: a module-level client would be shared
  // between users on the server and leak one person's cache into another's page.
  const [queryClient] = useState(makeQueryClient);
  const bootstrap = useSession((s) => s.bootstrap);
  const setTheme = useUi((s) => s.setTheme);

  useEffect(() => {
    setTheme(storedTheme());
    void bootstrap();
  }, [bootstrap, setTheme]);

  useEffect(() => {
    // Keep the socket's credential in step with the session: after a refresh
    // rotates the token, the old socket is authenticated with a token that no
    // longer exists, so it is replaced rather than left to fail silently.
    return onTokenChange((token) => {
      if (token) realtime.connect();
      else realtime.disconnect();
    });
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
