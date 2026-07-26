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

  setTheme: (theme: Theme) => void;
  setNavTab: (tab: NavTab) => void;
  openConversation: (id: string | null) => void;
  showList: () => void;
}

const THEME_KEY = "signal-clone:theme";

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

  setTheme: (theme) => {
    applyTheme(theme);
    set({ theme });
  },
  setNavTab: (navTab) => set({ navTab }),
  openConversation: (id) => set({ activeConversationId: id, mobilePane: id ? "chat" : "list" }),
  showList: () => set({ mobilePane: "list" }),
}));
