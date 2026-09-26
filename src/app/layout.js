import "./globals.css";

export const metadata = {
  title: "TIFF Merger",
  description:
    "Merge multiple TIFF images into a single multi-page TIFF file in your browser.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
