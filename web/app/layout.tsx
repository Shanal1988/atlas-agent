import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Atlas — Equity Research Agent",
  description: "Long-term equity research powered by Atlas AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100">
        <nav className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
            <Link href="/" className="font-bold text-white tracking-tight text-lg flex items-center gap-2">
              <span className="text-blue-400">▲</span> Atlas
            </Link>
            <Link href="/" className="text-sm text-slate-400 hover:text-white transition-colors">Analyse</Link>
            <Link href="/history" className="text-sm text-slate-400 hover:text-white transition-colors">History</Link>
            <Link href="/compare" className="text-sm text-slate-400 hover:text-white transition-colors">Compare</Link>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto w-full px-4 py-8 flex-1">{children}</main>
      </body>
    </html>
  );
}
