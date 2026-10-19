"use client";

import { SignIn } from "@clerk/nextjs";

export function ClerkSignInPanel() {
  return (
    <div className="stack" style={{ alignItems: "center" }}>
      <div className="panel" style={{ maxWidth: 420, width: "100%" }}>
        <h2>Sign in</h2>
        <p className="muted">
          Clerk session → Bearer JWT to FastAPI. Set{" "}
          <code>publicMetadata.role</code> to <code>admin</code>, <code>buyer</code>, or{" "}
          <code>contributor</code>.
        </p>
        <SignIn routing="hash" />
      </div>
    </div>
  );
}
