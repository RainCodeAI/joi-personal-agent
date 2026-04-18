import type { ReactNode } from "react";
import type { Metadata } from "next";

import "@/app/globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "Joi v2",
  description: "Next.js shell for Joi v2",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
