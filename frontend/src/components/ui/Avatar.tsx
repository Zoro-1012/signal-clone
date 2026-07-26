"use client";

import Image from "next/image";

import { avatarPalette, initials } from "@/lib/avatars";
import { cn } from "@/lib/cn";

const SIZES = {
  sm: "h-8 w-8 text-xs",
  md: "h-12 w-12 text-sm",
  lg: "h-14 w-14 text-base",
  xl: "h-20 w-20 text-2xl",
} as const;

interface AvatarProps {
  name: string;
  color?: string | null;
  src?: string | null;
  size?: keyof typeof SIZES;
  /** Renders the green presence dot. Omitted entirely for groups. */
  online?: boolean;
  className?: string;
}

/**
 * Circular avatar with an initials fallback.
 *
 * Signal renders initials as a pale field with saturated same-hue text rather
 * than white-on-solid, so the colours come from a bg/fg pair. The pair is chosen
 * server-side from a hash of the phone number, which keeps a person the same
 * colour on every device and after every reinstall.
 */
export function Avatar({
  name,
  color,
  src,
  size = "md",
  online,
  className,
}: AvatarProps) {
  const palette = avatarPalette(color);

  return (
    <div className={cn("relative shrink-0", className)}>
      {src ? (
        <Image
          src={src}
          alt=""
          width={96}
          height={96}
          className={cn("rounded-full object-cover", SIZES[size])}
        />
      ) : (
        <div
          className={cn(
            "flex items-center justify-center rounded-full font-medium select-none",
            SIZES[size],
          )}
          style={{ backgroundColor: palette.bg, color: palette.fg }}
          // The name is already rendered as text beside every avatar, so the
          // initials are decorative — announcing them would just repeat it.
          aria-hidden="true"
        >
          {initials(name)}
        </div>
      )}

      {online && (
        <span
          className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-surface-panel bg-signal-green"
          aria-label="Online"
        />
      )}
    </div>
  );
}
