import type { Metadata } from "next";
import { PageHeader } from "@/components/ui/Card";
import { ImageStudio } from "@/components/studio/ImageStudio";

export const metadata: Metadata = { title: "Image Studio", robots: { index: false } };

export default function StudioPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
      <PageHeader
        eyebrow="Development tool"
        title="Image Studio"
        description="Generate the photorealistic images for the home page with Gemini. Images are saved into the project and shown on the site, labelled as AI-generated."
      />
      <ImageStudio />
    </div>
  );
}
