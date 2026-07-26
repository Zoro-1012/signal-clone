import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge class names, letting later Tailwind utilities win over earlier ones.
 *
 * Plain concatenation leaves both `px-2` and `px-4` in the class list and the
 * winner is decided by stylesheet order, not call order — so a component's
 * override silently fails depending on how Tailwind happened to emit them.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
