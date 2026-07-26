"use client";

export function TypingIndicator({ names }: { names: string[] }) {
  if (names.length === 0) return null;

  const label =
    names.length === 1
      ? `${names[0]} is typing`
      : names.length === 2
        ? `${names[0]} and ${names[1]} are typing`
        : `${names.length} people are typing`;

  return (
    // aria-live=polite announces the change without interrupting whatever the
    // screen reader is currently saying.
    <div className="flex items-center gap-2 px-4 pb-1" aria-live="polite">
      <div className="flex items-center gap-1 rounded-bubble bg-bubble-in-bg px-3 py-2">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="h-1.5 w-1.5 animate-typing-bounce rounded-full bg-content-tertiary"
            style={{ animationDelay: `${index * 160}ms` }}
          />
        ))}
      </div>
      <span className="text-xs text-content-tertiary">{label}</span>
    </div>
  );
}
