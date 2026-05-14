export default function DashboardLoading() {
  return (
    <main className="container mx-auto px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="h-7 w-40 rounded-md bg-muted animate-pulse" />
        <div className="h-9 w-28 rounded-md bg-muted animate-pulse" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border bg-card p-4 space-y-3 animate-pulse"
          >
            <div className="h-5 w-1/2 rounded-md bg-muted" />
            <div className="h-3 w-2/3 rounded-md bg-muted" />
            <div className="h-3 w-1/3 rounded-md bg-muted" />
          </div>
        ))}
      </div>
    </main>
  );
}

