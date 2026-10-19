"use client";

import { type ReactNode, useCallback } from "react";
import { ClerkProvider, useAuth as useClerkAuth } from "@clerk/nextjs";
import { DevAuthProvider, SessionAuthBridge } from "@/lib/auth";

const clerkPk = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "";

function ClerkSessionInner({ children }: { children: ReactNode }) {
  const { getToken, isSignedIn, isLoaded } = useClerkAuth();
  const getAccessToken = useCallback(async () => {
    const t = await getToken();
    return t;
  }, [getToken]);

  return (
    <SessionAuthBridge
      getToken={getAccessToken}
      signedIn={!!isSignedIn}
      clerkLoaded={isLoaded}
    >
      {children}
    </SessionAuthBridge>
  );
}

/**
 * Auth root: Clerk when publishable key is set; otherwise structured local sessions (Bearer JWT).
 * UI never relies on a permanent "Act as" header switcher.
 */
export function AppProviders({ children }: { children: ReactNode }) {
  if (clerkPk) {
    return (
      <ClerkProvider publishableKey={clerkPk}>
        <ClerkSessionInner>{children}</ClerkSessionInner>
      </ClerkProvider>
    );
  }
  return <DevAuthProvider>{children}</DevAuthProvider>;
}

export function isClerkConfigured(): boolean {
  return Boolean(clerkPk);
}
