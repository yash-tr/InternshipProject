export default function EditorLoading() {
  return (
    <div className="flex h-screen flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b px-4 py-3">
        <div className="h-7 w-40 rounded-md bg-muted animate-pulse" />
        <div className="h-5 w-24 rounded-full bg-muted animate-pulse" />
        <div className="ml-auto h-8 w-24 rounded-md bg-muted animate-pulse" />
      </header>
      <div className="flex flex-1 min-h-0 lg:flex-row flex-col">
        <div className="w-full lg:w-[60%] overflow-y-auto border-r p-6 space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="rounded-lg border bg-card p-4 space-y-2 animate-pulse"
            >
              <div className="h-4 w-32 rounded-md bg-muted" />
              <div className="h-9 w-full rounded-md bg-muted" />
            </div>
          ))}
        </div>
        <div className="hidden lg:block w-[40%] overflow-y-auto bg-muted/30 p-6">
          <div className="h-full rounded-lg border border-dashed bg-background/60 animate-pulse" />
        </div>
      </div>
    </div>
  );
}

