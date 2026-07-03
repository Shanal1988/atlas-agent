import { NextRequest, NextResponse } from "next/server"

// Auth.js v5 stores the session JWT in this cookie
const COOKIE_NAME =
  process.env.NODE_ENV === "production"
    ? "__Secure-authjs.session-token"
    : "authjs.session-token"

export async function GET(req: NextRequest) {
  const rawJwt = req.cookies.get(COOKIE_NAME)?.value
  if (!rawJwt) return NextResponse.json({ error: "Not authenticated" }, { status: 401 })
  return NextResponse.json({ token: rawJwt })
}
