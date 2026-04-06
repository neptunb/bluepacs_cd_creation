import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BluePACS CD Creator",
  description: "Create DICOM CDs with embedded viewer for patients",
};

const RootLayout = ({ children }: { children: React.ReactNode }) => {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
};

export default RootLayout;
