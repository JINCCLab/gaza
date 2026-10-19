import { NextResponse } from "next/server";

/**
 * Placeholder matcher. When Clerk keys are set, swap to clerkMiddleware() from
 * @clerk/nextjs/server. Without keys we keep local Bearer sessions on /sign-in.
 */
export default function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
  ],
};
