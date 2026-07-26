"use client";

import { AuthScreen } from "@/features/auth/AuthScreen";
import { useSession } from "@/stores/session";

export default function HomePage() {
  const status = useSession((s) => s.status);
  const user = useSession((s) => s.user);

  // "loading" means the refresh cookie has not been checked yet. Rendering the
  // sign-in screen during that window would flash it at an already-signed-in
  // user on every page load.
  if (status === "loading") {
    return (
      <main className="flex h-dvh items-center justify-center bg-surface-base">
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-edge-subtle border-t-accent"
          role="status"
          aria-label="Loading"
        />
      </main>
    );
  }

  if (status === "anonymous" || !user) return <AuthScreen />;

  return (
    <main className="flex h-dvh items-center justify-center bg-surface-base">
      <p className="text-content-secondary">Signed in as {user.display_name}</p>
    </main>
  );
}
