"use client";

import { Bell, Database, LogOut, Monitor, Moon, Palette, Shield, Smartphone, Sun } from "lucide-react";

import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import type { UserPrivate } from "@/lib/types";
import { useSession } from "@/stores/session";
import { type Theme, useUi } from "@/stores/ui";

const THEMES: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
];

/** Sections the brief permits stubbing, shown as real rows rather than hidden. */
const PLACEHOLDERS = [
  { Icon: Shield, label: "Privacy", detail: "Read receipts, typing indicators, blocked users" },
  { Icon: Bell, label: "Notifications", detail: "Message alerts, sounds, previews" },
  { Icon: Smartphone, label: "Linked devices", detail: "Manage devices signed in to this account" },
  { Icon: Database, label: "Data usage", detail: "Media auto-download, storage" },
];

export function SettingsPane({ user }: { user: UserPrivate }) {
  const theme = useUi((s) => s.theme);
  const setTheme = useUi((s) => s.setTheme);
  const signOut = useSession((s) => s.signOut);

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-y-auto bg-surface-base">
      <header className="flex h-header shrink-0 items-center border-b border-edge-subtle px-6">
        <h1 className="text-lg font-semibold text-content-primary">Settings</h1>
      </header>

      <div className="mx-auto w-full max-w-2xl px-6 py-8">
        <section className="mb-8 flex items-center gap-4">
          <Avatar
            name={user.display_name}
            color={user.avatar_color}
            src={user.avatar_url}
            size="xl"
          />
          <div className="min-w-0">
            <h2 className="truncate text-xl font-semibold text-content-primary">
              {user.display_name}
            </h2>
            <p className="text-sm text-content-secondary">{user.phone_number}</p>
            {user.username && (
              <p className="text-sm text-content-secondary">@{user.username}</p>
            )}
          </div>
        </section>

        <section className="mb-8">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-content-secondary">
            <Palette className="h-4 w-4" aria-hidden="true" />
            Appearance
          </h3>
          {/* radiogroup rather than buttons: the options are mutually exclusive,
              and arrow keys should move between them. */}
          <div role="radiogroup" aria-label="Theme" className="flex gap-2">
            {THEMES.map(({ value, label, Icon }) => (
              <button
                key={value}
                role="radio"
                aria-checked={theme === value}
                onClick={() => setTheme(value)}
                className={cn(
                  "flex flex-1 flex-col items-center gap-2 rounded-xl border px-4 py-4 transition-colors",
                  theme === value
                    ? "border-accent bg-surface-hover text-content-primary"
                    : "border-edge-subtle text-content-secondary hover:bg-surface-hover",
                )}
              >
                <Icon className="h-5 w-5" />
                <span className="text-sm font-medium">{label}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <h3 className="mb-3 text-sm font-medium text-content-secondary">More</h3>
          <ul className="divide-y divide-edge-subtle overflow-hidden rounded-xl border border-edge-subtle">
            {PLACEHOLDERS.map(({ Icon, label, detail }) => (
              <li key={label}>
                <div className="flex items-center gap-3 px-4 py-3 opacity-60">
                  <Icon className="h-5 w-5 shrink-0 text-content-secondary" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-content-primary">{label}</p>
                    <p className="truncate text-sm text-content-secondary">{detail}</p>
                  </div>
                  <span className="shrink-0 rounded-full bg-surface-hover px-2 py-0.5 text-xs text-content-secondary">
                    Coming soon
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="mb-8">
          <Button variant="danger" onClick={() => void signOut()}>
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </section>

        <p className="text-xs leading-relaxed text-content-tertiary">
          A Signal clone built for the Scaler SDE assignment. Not affiliated with Signal
          Messenger. Encryption is simulated — messages are stored sealed, but the cipher is
          deliberately reversible and this app does not protect message contents.
        </p>
      </div>
    </div>
  );
}
