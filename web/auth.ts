import NextAuth from "next-auth"
import Google from "next-auth/providers/google"

const allowedEmails = process.env.ALLOWED_EMAILS?.split(",").map(e => e.trim()) ?? []

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  callbacks: {
    signIn({ user }) {
      if (allowedEmails.length === 0) return true // open if no allowlist set
      return allowedEmails.includes(user.email ?? "")
    },
    jwt({ token, account }) {
      if (account) token.sub = token.sub // preserve Google sub
      return token
    },
    session({ session, token }) {
      if (session.user) session.user.id = token.sub as string
      return session
    },
  },
  pages: { signIn: "/login" },
})
