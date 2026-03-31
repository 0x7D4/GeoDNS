import { Toaster } from 'sonner';
import HeroSection from './components/HeroSection';
import QuerySection from './components/QuerySection';

export default function App() {
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
      <HeroSection />
      <QuerySection />
    </>
  );
}
