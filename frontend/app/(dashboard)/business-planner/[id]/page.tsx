import { GuestExploreBanner } from "@/components/auth/GuestExploreBanner";
import { BusinessPlanDashboard } from "@/features/business-planner";

type Props = { params: Promise<{ id: string }> };

export default async function BusinessPlanDetailPage({ params }: Props) {
  const { id } = await params;
  return (
    <>
      <GuestExploreBanner action="keep this plan on your account" />
      <BusinessPlanDashboard planId={id} />
    </>
  );
}
