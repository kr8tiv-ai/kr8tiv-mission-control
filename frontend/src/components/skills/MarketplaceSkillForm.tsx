import { useState } from "react";

import { ApiError } from "@/api/mutator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type MarketplaceSkillFormValues = {
  sourceUrl: string;
  name: string;
  description: string;
};

type MarketplaceSkillFormProps = {
  initialValues?: MarketplaceSkillFormValues;
  sourceUrlReadOnly?: boolean;
  sourceUrlHelpText?: string;
  sourceLabel?: string;
  sourcePlaceholder?: string;
  nameLabel?: string;
  namePlaceholder?: string;
  descriptionLabel?: string;
  descriptionPlaceholder?: string;
  requiredUrlMessage?: string;
  submitLabel: string;
  submittingLabel: string;
  isSubmitting: boolean;
  onCancel: () => void;
  onSubmit: (values: MarketplaceSkillFormValues) => Promise<void>;
};

const DEFAULT_VALUES: MarketplaceSkillFormValues = {
  sourceUrl: "",
  name: "",
  description: "",
};

const extractErrorMessage = (error: unknown, fallback: string) => {
  if (error instanceof ApiError) return error.message || fallback;
  if (error instanceof Error) return error.message || fallback;
  return fallback;
};

export function MarketplaceSkillForm({
  initialValues,
  sourceUrlReadOnly = false,
  sourceUrlHelpText,
  sourceLabel = "Skill URL",
  sourcePlaceholder = "https://github.com/org/skill-repo",
  nameLabel = "Name (optional)",
  namePlaceholder = "Deploy Helper",
  descriptionLabel = "Description (optional)",
  descriptionPlaceholder = "Short summary shown in the marketplace.",
  requiredUrlMessage = "Skill URL is required.",
  submitLabel,
  submittingLabel,
  isSubmitting,
  onCancel,
  onSubmit,
}: MarketplaceSkillFormProps) {
  const resolvedInitial = initialValues ?? DEFAULT_VALUES;
  const [sourceUrl, setSourceUrl] = useState(resolvedInitial.sourceUrl);
  const [name, setName] = useState(resolvedInitial.name);
  const [description, setDescription] = useState(resolvedInitial.description);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedUrl = sourceUrl.trim();
    if (!normalizedUrl) {
      setErrorMessage(requiredUrlMessage);
      return;
    }

    setErrorMessage(null);

    try {
      await onSubmit({
        sourceUrl: normalizedUrl,
        name: name.trim(),
        description: description.trim(),
      });
    } catch (error) {
      setErrorMessage(extractErrorMessage(error, "Unable to save skill."));
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="space-y-5">
        <div className="space-y-2">
          <label
            htmlFor="source-url"
            className="text-xs font-semibold uppercase tracking-wider text-slate-500"
          >
            {sourceLabel}
          </label>
          <Input
            id="source-url"
            type="url"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            placeholder={sourcePlaceholder}
            readOnly={sourceUrlReadOnly}
            disabled={isSubmitting || sourceUrlReadOnly}
          />
          {sourceUrlHelpText ? (
            <p className="text-xs text-slate-500">{sourceUrlHelpText}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <label
            htmlFor="skill-name"
            className="text-xs font-semibold uppercase tracking-wider text-slate-500"
          >
            {nameLabel}
          </label>
          <Input
            id="skill-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={namePlaceholder}
            disabled={isSubmitting}
          />
        </div>

        <div className="space-y-2">
          <label
            htmlFor="skill-description"
            className="text-xs font-semibold uppercase tracking-wider text-slate-500"
          >
            {descriptionLabel}
          </label>
          <Textarea
            id="skill-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder={descriptionPlaceholder}
            className="min-h-[120px]"
            disabled={isSubmitting}
          />
        </div>

        {errorMessage ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            {errorMessage}
          </div>
        ) : null}
      </div>

      <div className="flex justify-end gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? submittingLabel : submitLabel}
        </Button>
      </div>
    </form>
  );
}
