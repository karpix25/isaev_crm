import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { TelegramProvider } from "@/components/TelegramProvider";
import Script from "next/script";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RepairCRM - Управление ремонтами",
  description: "CRM система для управления ремонтами квартир",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <head>
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <TelegramProvider>{children}</TelegramProvider>
      </body>
    </html>
  );
}
