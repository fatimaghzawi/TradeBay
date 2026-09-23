import { GuestExploreBanner } from "@/components/auth/GuestExploreBanner";
import { BusinessPlannerEntry } from "@/features/business-planner";

export default function BusinessPlannerPage() {
  return (
    <>
      <GuestExploreBanner action="keep AI plans permanently on your account" />
      <BusinessPlannerEntry />
    </>
  );
}
