"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { ApiError, api } from "@/lib/api";
import type { AuthChallenge, AuthSession } from "@/lib/types";
import { useSession } from "@/stores/session";

type Step = "phone" | "code" | "profile";
type Mode = "sign-in" | "register";

/** Signal's logo mark, redrawn: a speech bubble with a dashed outline. */
function SignalMark() {
  return (
    <svg viewBox="0 0 48 48" className="h-16 w-16" aria-hidden="true">
      <path
        d="M24 4C12.4 4 3 12.5 3 23c0 5.6 2.7 10.6 7 14l-2 6.5 7-3.4c2.8 1.2 5.9 1.9 9 1.9 11.6 0 21-8.5 21-19S35.6 4 24 4Z"
        fill="var(--accent)"
      />
    </svg>
  );
}

export function AuthScreen() {
  const signIn = useSession((s) => s.signIn);

  const [step, setStep] = useState<Step>("phone");
  const [mode, setMode] = useState<Mode>("sign-in");
  const [phone, setPhone] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function requestCode() {
    setBusy(true);
    setError(null);
    try {
      const path = mode === "register" ? "/auth/register" : "/auth/login";
      const body =
        mode === "register"
          ? { phone_number: phone, display_name: displayName.trim() }
          : { phone_number: phone };
      const challenge = await api.post<AuthChallenge>(path, body);
      setDevCode(challenge.dev_code);
      // The mocked code is surfaced in development so a reviewer can complete
      // onboarding without an SMS provider; production omits it entirely.
      setCode(challenge.dev_code ?? "");
      setStep("code");
    } catch (err) {
      if (err instanceof ApiError) {
        // A number that is not registered is not an error the user made — it
        // just means they need to create an account, so offer that directly.
        if (err.code === "account_not_found") {
          setMode("register");
          setStep("profile");
          setError(null);
          return;
        }
        if (err.code === "phone_taken") {
          setMode("sign-in");
          setError("That number is already registered. Signing you in instead.");
          setStep("phone");
          return;
        }
        setError(err.message);
      } else {
        setError("Could not reach the server. Check your connection.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      const session = await api.post<AuthSession>("/auth/verify", {
        phone_number: phone,
        code,
      });
      signIn(session.user, session.access_token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-surface-base px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <SignalMark />
          <h1 className="mt-6 text-2xl font-semibold text-content-primary">
            {step === "profile" ? "Create your account" : "Signal"}
          </h1>
          <p className="mt-2 text-sm text-content-secondary">
            {step === "phone" && "Enter your phone number to get started."}
            {step === "profile" && "Tell us what to call you."}
            {step === "code" && `We sent a code to ${phone}.`}
          </p>
        </div>

        {step === "phone" && (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void requestCode();
            }}
          >
            <Input
              label="Phone number"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              autoFocus
              placeholder="+91 98765 43210"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              error={error}
              hint="Include your country code."
            />
            <Button type="submit" size="lg" fullWidth loading={busy} disabled={phone.length < 6}>
              Continue
            </Button>
          </form>
        )}

        {step === "profile" && (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void requestCode();
            }}
          >
            <Input
              label="Your name"
              autoFocus
              autoComplete="name"
              placeholder="Nipurn Goyal"
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              error={error}
              hint="This is what other people will see."
            />
            <Button
              type="submit"
              size="lg"
              fullWidth
              loading={busy}
              disabled={displayName.trim().length < 1}
            >
              Create account
            </Button>
            <Button
              type="button"
              variant="ghost"
              fullWidth
              onClick={() => {
                setStep("phone");
                setError(null);
              }}
            >
              Back
            </Button>
          </form>
        )}

        {step === "code" && (
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void verify();
            }}
          >
            <Input
              label="Verification code"
              inputMode="numeric"
              autoComplete="one-time-code"
              autoFocus
              maxLength={6}
              placeholder="123456"
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
              error={error}
              className="text-center text-2xl tracking-[0.5em]"
            />

            {devCode && (
              <p className="rounded-lg bg-surface-hover px-4 py-3 text-center text-sm text-content-secondary">
                Verification is simulated for this demo. Your code is{" "}
                <span className="font-mono font-semibold text-content-primary">{devCode}</span>.
              </p>
            )}

            <Button type="submit" size="lg" fullWidth loading={busy} disabled={code.length < 4}>
              Verify
            </Button>
            <Button
              type="button"
              variant="ghost"
              fullWidth
              onClick={() => {
                setStep("phone");
                setCode("");
                setError(null);
              }}
            >
              Use a different number
            </Button>
          </form>
        )}

        <p className="mt-10 text-center text-xs text-content-tertiary">
          A Signal clone built for the Scaler SDE assignment. Not affiliated with Signal
          Messenger. Encryption is simulated.
        </p>
      </div>
    </main>
  );
}
