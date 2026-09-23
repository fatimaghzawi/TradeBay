import { redirect } from "next/navigation";

type Props = { params: Promise<{ id: string }> };

/** Legacy path — negotiations live under /negotiations/[id]. */
export default async function LegacyNegotiationRedirect({ params }: Props) {
  const { id } = await params;
  redirect(`/conversations/${id}`);
}
