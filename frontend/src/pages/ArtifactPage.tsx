// Artifact reading view (S — the Return). Placeholder; the full article + click-to-trace
// provenance lands in 4C.

export function ArtifactPage({ huntId }: { huntId: string }) {
  return (
    <div className="fixed inset-0 bg-door-bg text-white font-sans flex items-center justify-center">
      <p className="text-door-dim text-sm">Artifact for {huntId}</p>
    </div>
  );
}
