"use client";

import { useSession } from "@/stores/session";

export default function HomePage() {
  const status = useSession((s) => s.status);
  const user = useSession((s) => s.user);

  if (status === "loading") {
    return (
      <main className="flex h-dvh items-center justify-center bg-surface-base">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-edge-subtle border-t-accent" />
      </main>
    );
  }

  return (
    <main className="flex h-dvh items-center justify-center bg-surface-base">
      <p className="text-content-secondary">
        {user ? `Signed in as ${user.display_name}` : "Not signed in"}
      </p>
    </main>
  );
}
