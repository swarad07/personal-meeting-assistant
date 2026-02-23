import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { StatusBar } from "@/components/layout/StatusBar";
import { CommandMenu } from "@/components/layout/CommandMenu";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { Toaster } from "sonner";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Meeting Assistant",
  description: "Personal Meeting Assistant - AI-powered meeting intelligence",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${dmSans.variable} font-sans antialiased`}>
        <QueryProvider>
          <div className="flex h-screen overflow-hidden bg-surface">
            <Sidebar />
            <div className="flex flex-1 flex-col overflow-hidden">
              <main className="flex-1 overflow-y-auto">{children}</main>
              <StatusBar />
            </div>
          </div>
          <CommandMenu />
          <Toaster
            position="top-right"
            richColors
            toastOptions={{
              className: "font-sans",
              duration: 4000,
            }}
          />
        </QueryProvider>
      </body>
    </html>
  );
}
