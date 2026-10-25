import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MudraCard } from "@/components/mudras/MudraCard";
import { ConceptResults } from "@/components/learning/ConceptResults";
import { ErrorState, EmptyState } from "@/components/ui/StatusStates";
import { PredictionTimeline } from "@/components/results/PredictionTimeline";
import { ApiError } from "@/types/api";
import type { ConceptResult } from "@/types/knowledge";

const mudra = { id: 3, name: "Alapadma", hasta_type: "asamyuta" as const, meaning: "Full-blown lotus", image_url: "/static/alapadma.jpg" };

describe("MudraCard", () => {
  it("renders the name, meaning and backend image", () => {
    render(<MudraCard mudra={mudra} />);
    expect(screen.getByRole("heading", { name: "Alapadma" })).toBeInTheDocument();
    expect(screen.getByText("Full-blown lotus")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /reference image of the alapadma/i })).toHaveAttribute("src", "http://localhost:8000/static/alapadma.jpg");
  });

  it("shows a labelled placeholder when the image is missing", () => {
    render(<MudraCard mudra={{ ...mudra, image_url: null }} />);
    expect(screen.getByRole("img", { name: /no reference image available/i })).toBeInTheDocument();
  });

  it("swaps to the placeholder when the image fails to load", () => {
    render(<MudraCard mudra={mudra} />);
    fireEvent.error(screen.getByRole("img", { name: /reference image of the alapadma/i }));
    expect(screen.getByText(/reference image not available/i)).toBeInTheDocument();
  });

  it("only offers practice when a practice reference exists", () => {
    const { rerender } = render(<MudraCard mudra={mudra} />);
    expect(screen.queryByRole("link", { name: /start practice/i })).not.toBeInTheDocument();
    rerender(<MudraCard mudra={mudra} practiceReferenceId={9} />);
    expect(screen.getByRole("link", { name: /start practice/i })).toHaveAttribute("href", "/practice/9");
  });
});

describe("ConceptResults", () => {
  const concepts: ConceptResult[] = [
    {
      concept: "garden",
      supported: true,
      matches: [
        { ...mudra, id: 1, name: "Option One", rationale: "Because flowers", source: "KB" },
        { ...mudra, id: 2, name: "Option Two", rationale: null, source: null },
      ],
    },
    { concept: "krishna", supported: false, matches: [] },
  ];

  it("shows alternatives and the knowledge base's rationale", () => {
    render(<ConceptResults concepts={concepts} />);
    expect(screen.getByText("2 possible interpretations")).toBeInTheDocument();
    expect(screen.getByText("Option 1")).toBeInTheDocument();
    expect(screen.getByText("Because flowers")).toBeInTheDocument();
  });

  it("lists unsupported concepts instead of inventing a mudra", () => {
    render(<ConceptResults concepts={concepts} />);
    expect(screen.getByRole("heading", { name: /not in the knowledge base yet/i })).toBeInTheDocument();
    expect(screen.getByText("krishna")).toBeInTheDocument();
  });

  it("shows a helpful notice for an empty response", () => {
    render(<ConceptResults concepts={[]} />);
    expect(screen.getByText(/no concepts in your text matched/i)).toBeInTheDocument();
  });
});

describe("status states", () => {
  it("ErrorState shows a friendly message and a retry button", () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new ApiError("network", "x")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/could not reach the nrityaguru server/i);
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("EmptyState renders its title", () => {
    render(<EmptyState title="No practice sessions yet" />);
    expect(screen.getByRole("heading", { name: "No practice sessions yet" })).toBeInTheDocument();
  });
});

describe("PredictionTimeline", () => {
  it("renders predictions with time ranges from fps", () => {
    render(<PredictionTimeline predictions={[{ label: "Pataka", confidence: 0.91, frame_start: 0, frame_end: 29 }]} framesTotal={60} fps={30} />);
    expect(screen.getByText("Pataka")).toBeInTheDocument();
    expect(screen.getByText(/0\.0 s – 1\.0 s · model confidence 91%/)).toBeInTheDocument();
  });

  it("explains when there are no predictions", () => {
    render(<PredictionTimeline predictions={[]} framesTotal={60} fps={30} />);
    expect(screen.getByText(/no gesture predictions/i)).toBeInTheDocument();
  });
});
