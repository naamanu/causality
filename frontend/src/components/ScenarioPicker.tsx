import type { ScenarioSummary } from "../api/types";

interface Props {
  scenarios: ScenarioSummary[];
  selectedIncidentId: string | null;
  onSelect: (incidentId: string) => void;
}

export function ScenarioPicker({ scenarios, selectedIncidentId, onSelect }: Props) {
  return (
    <div className="space-y-1.5">
      <div className="text-[11px] uppercase tracking-widest text-zinc-500 mb-2">
        Scenarios
      </div>
      {scenarios.map((s) => {
        const active = s.incident_id === selectedIncidentId;
        return (
          <button
            key={s.scenario_key}
            onClick={() => onSelect(s.incident_id)}
            className={[
              "w-full text-left rounded-md px-3 py-2.5 border transition-colors",
              active
                ? "border-accent/40 bg-ink-850"
                : "border-transparent hover:bg-ink-900",
            ].join(" ")}
          >
            <div className="flex items-center gap-2">
              <span
                className={[
                  "h-1.5 w-1.5 rounded-full",
                  active ? "bg-accent" : "bg-ink-600",
                ].join(" ")}
              />
              <span className="text-sm text-zinc-200">{s.title}</span>
            </div>
            <p className="mt-1 pl-3.5 text-xs leading-relaxed text-zinc-500">
              {s.description}
            </p>
          </button>
        );
      })}
    </div>
  );
}
