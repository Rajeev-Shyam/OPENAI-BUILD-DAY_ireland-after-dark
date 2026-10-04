import ApiStatus from "@/components/ApiStatus";
import MapView from "@/components/MapView";

export default function HomePage() {
  return (
    <main className="h-screen">
      <header className="flex items-center gap-3 bg-night px-4 py-2 text-white">
        <h1 className="text-lg font-semibold">Ireland After Dark</h1>
        <ApiStatus />
      </header>
      <MapView />
    </main>
  );
}
