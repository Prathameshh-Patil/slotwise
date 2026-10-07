import { Suspense } from "react";

import { SeatPicker } from "@/components/seat-picker";

// The event id is only known at request time, so the part that reads it sits
// inside Suspense; the rest of the page can be prerendered.
export default function EventPage({ params }: PageProps<"/events/[id]">) {
  return (
    <Suspense fallback={<p className="text-muted">Loading event…</p>}>
      <EventView params={params} />
    </Suspense>
  );
}

async function EventView({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SeatPicker eventId={Number(id)} />;
}
