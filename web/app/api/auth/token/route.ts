import { auth } from "@/auth"
import { NextResponse } from "next/server"
import { SignJWT } from "jose"

export async function GET() {
  const session = await auth()
  if (!session?.user) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 })
  }

  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET)
  const token = await new SignJWT({
    sub: session.user.id ?? session.user.email,
    email: session.user.email,
    name: session.user.name,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(secret)

  return NextResponse.json({ token })
}
