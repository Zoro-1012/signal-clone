"use client";

import { useEffect } from "react";

import { useUi } from "@/stores/ui";

/** The id the conversation search input carries, so ⌘K can find it. */
export const SEARCH_INPUT_ID = "conversation-search";

/**
 * Application-wide keyboard shortcuts.
 *
 * Deliberately few. Every shortcut claims a key combination from the browser
 * and from assistive technology, so each one has to earn it: ⌘K reaches search
 * and ⌘N starts a chat, which are the two things a messenger is opened to do.
 *
 * Nothing fires while the caret is in a field — otherwise ⌘N inside the
 * composer would interrupt someone mid-sentence, which is precisely when they
 * least want a modal.
 */
export function useGlobalShortcuts({ onNewChat }: { onNewChat: () => void }): void {
  const setNavTab = useUi((s) => s.setNavTab);
  const showList = useUi((s) => s.showList);

  useEffect(() => {
    function handle(event: KeyboardEvent) {
      if (!event.metaKey && !event.ctrlKey) return;

      const key = event.key.toLowerCase();
      if (key !== "k" && key !== "n") return;

      // A modifier chord is safe inside a field, but only for keys the field
      // does not already own; bail on anything with a text caret to be sure.
      const target = event.target as HTMLElement | null;
      const editing =
        target?.isContentEditable ||
        ["INPUT", "TEXTAREA", "SELECT"].includes(target?.tagName ?? "");

      if (key === "k") {
        event.preventDefault();
        setNavTab("chats");
        showList();
        // The list may have been unmounted on a phone, so focus on the next
        // frame rather than against the tree being replaced.
        requestAnimationFrame(() => {
          const input = document.getElementById(SEARCH_INPUT_ID);
          if (input instanceof HTMLInputElement) {
            input.focus();
            input.select();
          }
        });
        return;
      }

      if (key === "n" && !editing) {
        event.preventDefault();
        setNavTab("chats");
        onNewChat();
      }
    }

    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [onNewChat, setNavTab, showList]);
}
