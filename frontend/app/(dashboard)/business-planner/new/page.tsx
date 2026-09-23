import { GuestExploreBanner } from "@/components/auth/GuestExploreBanner";
import { BusinessPlannerDiscovery } from "@/features/business-planner";

export default function BusinessPlannerNewPage() {
  return (
    <>
      <GuestExploreBanner action="keep AI plans permanently on your account" />
      <BusinessPlannerDiscovery />
    </>
  );
}
