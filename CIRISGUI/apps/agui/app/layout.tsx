import './globals.css';
import type { ReactNode } from 'react';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <aside className="sidebar">CIRIS</aside>
        <main>{children}</main>
      </body>
    </html>
  );
}
