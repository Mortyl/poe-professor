"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import Navbar from "../../components/Navbar";
import styles from "./signin.module.css";

const ERROR_MESSAGES: Record<string, string> = {
  OAuthSignin: "Something went wrong starting the sign-in flow. Try again.",
  OAuthCallback: "Provider callback failed. Check that the redirect URI matches the OAuth app config.",
  OAuthCreateAccount: "Could not create an account from this provider response.",
  Callback: "Authentication callback failed.",
  AccessDenied: "Sign-in was cancelled or access was denied.",
  Verification: "The sign-in link expired. Try again.",
  Configuration: "Auth is misconfigured. Check the AUTH_*_ID / AUTH_*_SECRET values in .env.local.",
  Default: "Something went wrong signing in.",
};

export default function SignInPage() {
  const searchParams = useSearchParams();
  const error = searchParams.get("error");
  const callbackUrl = searchParams.get("callbackUrl") ?? "/";

  const errorMessage = error ? (ERROR_MESSAGES[error] ?? ERROR_MESSAGES.Default) : null;

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.card}>
          <div className={styles.flourish}>
            <span className={styles.flourishLine} />
            <span className={styles.flourishDiamond} />
            <span className={`${styles.flourishDiamond} ${styles.flourishCenter}`} />
            <span className={styles.flourishDiamond} />
            <span className={styles.flourishLine} />
          </div>
          <h1 className={styles.title}>SIGN IN</h1>
          <p className={styles.blurb}>
            Sign in with Discord to save your character analyses and pin your favourite build guides.
          </p>

          {errorMessage && <div className={styles.error}>{errorMessage}</div>}

          <div className={styles.providerStack}>
            <button
              className={styles.discordBtn}
              onClick={() => signIn("discord", { callbackUrl })}
            >
              <DiscordIcon />
              <span>Continue with Discord</span>
            </button>
            <button
              className={styles.googleBtn}
              onClick={() => signIn("google", { callbackUrl })}
            >
              <GoogleIcon />
              <span>Continue with Google</span>
            </button>
          </div>

          <p className={styles.fine}>
            By signing in you agree we&apos;ll store your name, email and avatar from the chosen provider
            so we can attribute your saved data to you. You can sign out and delete your account at any time.
          </p>
        </div>
      </main>
    </>
  );
}

// ── Inline SVG icons (no external deps; sized via the .icon class) ───────

function DiscordIcon() {
  return (
    <svg
      className={styles.icon}
      viewBox="0 0 127.14 96.36"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <path
        fill="currentColor"
        d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,46,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.25,60,73.25,53s5-12.74,11.44-12.74S96.23,46,96.12,53,91.08,65.69,84.69,65.69Z"
      />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg
      className={styles.icon}
      viewBox="0 0 48 48"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z" />
      <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z" />
      <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z" />
      <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z" />
    </svg>
  );
}
