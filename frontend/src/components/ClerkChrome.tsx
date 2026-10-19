"use client";

import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";
import type { User } from "@/lib/api";

export function ClerkChrome({ user }: { user: User | null }) {
  return (
    <>
      <SignedOut>
        <SignInButton mode="modal">
          <button type="button">Sign in</button>
        </SignInButton>
      </SignedOut>
      <SignedIn>
        {user && (
          <span className="muted">
            <span className="badge">{user.role}</span> {user.email}
          </span>
        )}
        <UserButton />
      </SignedIn>
    </>
  );
}
