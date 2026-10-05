/** Heatmap layers the tumor world can record, in display order. */
export const FIELD_STYLE: Record<string, { label: string; color: string }> = {
  drug: { label: "Drug", color: "--primary" },
  oxygen: { label: "Oxygen", color: "--info" },
  trail_pheromone: { label: "Trail", color: "--success" },
  alarm_pheromone: { label: "Alarm", color: "--danger" },
  recruitment_pheromone: { label: "Recruit", color: "--warning" },
};
