"use client";

import { create } from "zustand";

import { api, setAccessToken } from "@/lib/api";
import { realtime } from "@/lib/ws";
import type { UserPrivate } from "@/lib/types";

interface SessionState {
  user: UserPrivate | null;
  /** Distinguishes "not signed in" from "we have not checked yet". */
  status: "loading" | "authenticated" | "anonymous";
  signIn: (user: UserPrivate, accessToken: string) => void;
  signOut: () => Promise<void>;
  /** Trade the httpOnly refresh cookie for a session on page load. */
  bootstrap: () => Promise<void>;
}

export const useSession = create<SessionState>((set) => ({
  user: null,
  status: "loading",

  signIn: (user, accessToken) => {
    setAccessToken(accessToken);
    set({ user, status: "authenticated" });
    realtime.connect();
  },

  signOut: async () => {
    realtime.disconnect();
    try {
      await api.post("/auth/logout");
    } catch {
      // Logout is best-effort: the local session is cleared regardless, so a
      // network failure cannot strand someone in a signed-in-looking state.
    }
    setAccessToken(null);
    set({ user: null, status: "anonymous" });
  },

  bootstrap: async () => {
    const token = await api.refresh();
    if (!token) {
      set({ user: null, status: "anonymous" });
      return;
    }
    try {
      const user = await api.get<UserPrivate>("/users/me");
      set({ user, status: "authenticated" });
      realtime.connect();
    } catch {
      setAccessToken(null);
      set({ user: null, status: "anonymous" });
    }
  },
}));
