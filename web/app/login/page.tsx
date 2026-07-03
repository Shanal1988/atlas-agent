"use client"
import { signIn } from "next-auth/react"

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center space-y-6">
        <div className="text-blue-400 text-4xl">▲</div>
        <h1 className="text-3xl font-bold text-white">Atlas Agent</h1>
        <p className="text-slate-400">Investment analysis powered by AI</p>
        <button
          onClick={() => signIn("google", { callbackUrl: "/" })}
          className="bg-white text-slate-900 px-6 py-3 rounded-lg font-medium hover:bg-slate-100 transition-colors"
        >
          Sign in with Google
        </button>
      </div>
    </div>
  )
}
