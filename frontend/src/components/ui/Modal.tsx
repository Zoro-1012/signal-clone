"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Announced to screen readers; omit when the title is self-explanatory. */
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/**
 * Dialog built on Radix.
 *
 * Radix supplies the parts that are easy to get wrong and invisible when they
 * are: the focus trap, restoring focus to the trigger on close, Escape and
 * outside-click handling, `aria-modal`, and inert-ing the rest of the page.
 * Only the appearance is ours.
 */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
}: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-modal bg-surface-overlay animate-fade-in" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-modal w-[min(28rem,calc(100vw-2rem))]",
            "-translate-x-1/2 -translate-y-1/2 animate-slide-up",
            "rounded-2xl border border-edge-subtle bg-surface-raised shadow-2xl",
            "flex max-h-[min(40rem,calc(100vh-4rem))] flex-col",
            className,
          )}
        >
          <header className="flex items-center justify-between border-b border-edge-subtle px-5 py-4">
            <Dialog.Title className="text-lg font-semibold text-content-primary">
              {title}
            </Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              className="rounded-full p-1.5 text-content-secondary transition-colors hover:bg-surface-hover"
            >
              <X className="h-5 w-5" />
            </Dialog.Close>
          </header>

          {description && (
            <Dialog.Description className="px-5 pt-3 text-sm text-content-secondary">
              {description}
            </Dialog.Description>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>

          {footer && (
            <footer className="border-t border-edge-subtle px-5 py-3">{footer}</footer>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
