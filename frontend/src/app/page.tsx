import { SystemStatus } from "@/components/system/SystemStatus";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";

const UPCOMING: { title: string; phase: number }[] = [
  { title: "Recent Projects", phase: 2 },
  { title: "Active Jobs", phase: 3 },
  { title: "Recent Generations", phase: 5 },
  { title: "Influencers", phase: 6 },
  { title: "Products", phase: 8 },
  { title: "Properties", phase: 17 },
];

export default function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Local system status and recent work." />
      <SystemStatus />
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {UPCOMING.map(({ title, phase }) => (
          <Card key={title} title={title}>
            <EmptyState title="Nothing here yet">Available from Phase {phase}.</EmptyState>
          </Card>
        ))}
      </div>
    </>
  );
}
