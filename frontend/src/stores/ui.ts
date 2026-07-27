"use client";

import { create } from "zustand";

export type Theme = "light" | "dark" | "system";
export type NavTab = "chats" | "calls" | "stories" | "settings";

interface UiState {
  theme: Theme;
  navTab: NavTab;
  /** Which conversation the chat pane is showing; null shows the empty state. */
  activeConversationId: string | null;
  /** Mobile only: which pane is visible, since both cannot fit. */
  mobilePane: "list" | "chat";
  /** Desktop only: whether the nav rail is shown. Signal calls this "tabs". */
  railVisible: boolean;
  /** Narrow the list to conversations with something unread. */
  unreadOnly: boolean;

  setTheme: (theme: Theme) => void;
  setNavTab: (tab: NavTab) => void;
  openConversation: (id: string | null) => void;
  showList: () => void;
  toggleRail: () => void;
  setUnreadOnly: (value: boolean) => void;
}

const THEME_KEY = "signal-clone:theme";
const RAIL_KEY = "signal-clone:rail-visible";

/** Chrome preferences belong to the device, so they survive a reload. */
function storedRailVisible(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(RAIL_KEY) !== "false";
}

function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  const prefersDark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", prefersDark);
  localStorage.setItem(THEME_KEY, theme);
}

export function storedTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  return (localStorage.getItem(THEME_KEY) as Theme | null) ?? "dark";
}

export const useUi = create<UiState>((set) => ({
  theme: "dark",
  navTab: "chats",
  activeConversationId: null,
  mobilePane: "list",
  // Server-rendered markup must match the first client render, so this starts
  // at the default and is reconciled from storage after mount.
  railVisible: true,
  unreadOnly: false,

  setTheme: (theme) => {
    applyTheme(theme);
    set({ theme });
  },
  setNavTab: (navTab) => set({ navTab }),
  openConversation: (id) => set({ activeConversationId: id, mobilePane: id ? "chat" : "list" }),
  showList: () => set({ mobilePane: "list" }),
  toggleRail: () =>
    set((state) => {
      const railVisible = !state.railVisible;
      if (typeof window !== "undefined") {
        localStorage.setItem(RAIL_KEY, String(railVisible));
      }
      return { railVisible };
    }),
  setUnreadOnly: (unreadOnly) => set({ unreadOnly }),
}));

/** Re-apply the stored rail preference once the client has taken over. */
export function hydrateRailPreference(): void {
  useUi.setState({ railVisible: storedRailVisible() });
}
