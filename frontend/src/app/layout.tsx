import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AI Influencer Studio",
  description: "Local-first AI content studio",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
