import { DashboardLists } from "@/components/dashboard/DashboardLists";
import { SystemStatus } from "@/components/system/SystemStatus";
import { PageHeader } from "@/components/ui/PageHeader";

export default function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Local system status and recent work." />
      <SystemStatus />
      <DashboardLists />
    </>
  );
}
