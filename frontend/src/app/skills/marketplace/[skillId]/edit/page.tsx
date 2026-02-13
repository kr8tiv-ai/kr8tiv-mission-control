import { redirect } from "next/navigation";

type EditMarketplaceSkillPageProps = {
  params: Promise<{ skillId: string }>;
};

export default async function EditMarketplaceSkillPage({
  params,
}: EditMarketplaceSkillPageProps) {
  const { skillId } = await params;
  redirect(`/skills/packs/${skillId}/edit`);
}
