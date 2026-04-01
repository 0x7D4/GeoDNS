import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import HeroSection from './components/HeroSection';

export type LocateData = {
  ip: string;
  city: string;
  region: string;
  is_india: boolean;
  nearest_anchor: { id: string; city: string };
} | null;

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export default function App() {
  const [locateData, setLocateData] = useState<LocateData>(null);

  useEffect(() => {
    async function getLocate() {
      try {
        const res = await fetch(`${API_BASE}/api/locate`);
        if (!res.ok) return;
        const data = await res.json();
        setLocateData({
          ip: data.location.ip,
          city: data.location.city,
          region: data.location.region,
          is_india: data.location.is_india,
          nearest_anchor: {
            id: data.nearest_anchor.id,
            city: data.nearest_anchor.city
          }
        });
      } catch (err) {
        console.error('Locate failed:', err);
      }
    }
    getLocate();
  }, []);

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'hsl(0, 0%, 10%)',
            color: '#fff',
            border: '1px solid hsl(0, 0%, 18%)',
          },
        }}
      />
      <HeroSection locateData={locateData} />
    </>
  );
}
