import { EpisodeFormat } from "../types";

const FORMATS: { id: EpisodeFormat; label: string; description: string }[] = [
  {
    id: "monologue",
    label: "Monologue",
    description: "A single narrator walks you through the topic solo.",
  },
  {
    id: "interview",
    label: "Guest Expert Interview",
    description: "A host interviews a practitioner/researcher in the field — shows what the discipline looks like in practice.",
  },
  {
    id: "two_host",
    label: "Two-Host Conversation",
    description: "Two co-hosts think it through together, including constructive disagreement.",
  },
  {
    id: "debate",
    label: "Debate / Steelman",
    description: "Two well-developed, fairly-argued positions — good for contested topics.",
  },
];

interface Props {
  selected: EpisodeFormat | null;
  onSelect: (format: EpisodeFormat) => void;
}

export default function FormatSelector({ selected, onSelect }: Props) {
  return (
    <div>
      <h4>Format</h4>
      <div className="option-group">
        {FORMATS.map((f) => (
          <div
            key={f.id}
            className={`option-card${selected === f.id ? " selected" : ""}`}
            onClick={() => onSelect(f.id)}
          >
            <h4>{f.label}</h4>
            <p>{f.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
