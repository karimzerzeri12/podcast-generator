import { Voice } from "../types";

interface Props {
  voices: Voice[];
  selected: string | null;
  onSelect: (voiceId: string) => void;
  label?: string;
}

export default function VoiceSelector({ voices, selected, onSelect, label = "Voice" }: Props) {
  return (
    <div>
      <h4>{label}</h4>
      <div className="option-group">
        {voices.map((v) => (
          <div
            key={v.id}
            className={`option-card${selected === v.id ? " selected" : ""}`}
            onClick={() => onSelect(v.id)}
          >
            <h4>{v.name}</h4>
            {v.description && <p>{v.description}</p>}
            {v.preview_url && (
              <audio
                controls
                src={v.preview_url}
                style={{ width: "100%", marginTop: "0.5rem", height: 32 }}
                onClick={(e) => e.stopPropagation()}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
