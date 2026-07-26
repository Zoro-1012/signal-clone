/**
 * Avatar colours.
 *
 * Signal renders an initials avatar as a *pale* background with a saturated
 * foreground of the same hue — not a solid block of colour. Matching that pairing
 * is most of what makes the conversation list read as Signal rather than as a
 * generic chat app.
 *
 * The backend stores a stable colour name per user (derived from a hash of their
 * phone number, so it never changes). This maps that name to the pair.
 */

export type AvatarColorName =
  | "ultramarine"
  | "crimson"
  | "vermilion"
  | "burlap"
  | "forest"
  | "wintergreen"
  | "teal"
  | "blue"
  | "indigo"
  | "violet"
  | "plum"
  | "taupe"
  | "steel";

interface AvatarPalette {
  /** Pale fill behind the initials. */
  bg: string;
  /** Saturated colour of the initials themselves. */
  fg: string;
}

const PALETTE: Record<AvatarColorName, AvatarPalette> = {
  ultramarine: { bg: "#dde7fc", fg: "#1251d3" },
  crimson: { bg: "#f5d7d7", fg: "#be0404" },
  vermilion: { bg: "#f5e0d7", fg: "#c73f0a" },
  burlap: { bg: "#eae6d5", fg: "#7d6f40" },
  forest: { bg: "#cde4cd", fg: "#067906" },
  wintergreen: { bg: "#cfe8de", fg: "#1d8663" },
  teal: { bg: "#d8e8f0", fg: "#086da0" },
  blue: { bg: "#d8e4f0", fg: "#336ba3" },
  indigo: { bg: "#e3e3fe", fg: "#3838f5" },
  violet: { bg: "#f5e3fe", fg: "#9f00f0" },
  plum: { bg: "#f6d8ec", fg: "#b8057c" },
  taupe: { bg: "#f0e0e3", fg: "#8f616a" },
  steel: { bg: "#d2d2dc", fg: "#4f4f6d" },
};

const FALLBACK: AvatarPalette = PALETTE.steel;

export function avatarPalette(name: string | null | undefined): AvatarPalette {
  if (!name) return FALLBACK;
  return PALETTE[name as AvatarColorName] ?? FALLBACK;
}

/**
 * One or two letters for the avatar.
 *
 * Mirrors the backend's rule so the same person shows the same initials
 * everywhere, including in payloads the client renders optimistically before the
 * server has replied.
 */
export function initials(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}
