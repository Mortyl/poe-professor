/**
 * Auth.js dynamic route handlers — handles /api/auth/* (sign-in, callback,
 * session, signout, etc). Don't add logic here; configure in `auth.ts`.
 */
import { handlers } from "@/auth";
export const { GET, POST } = handlers;
