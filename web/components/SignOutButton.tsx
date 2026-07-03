"use client"
import { signOut } from "next-auth/react"

export function SignOutButton() {
  return (
    <button
      onClick={() => signOut({ callbackUrl: "/login" })}
      className="text-xs text-slate-400 hover:text-white transition-colors"
    >
      Sign out
    </button>
  )
}
