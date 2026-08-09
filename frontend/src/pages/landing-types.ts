import type { MutableRefObject } from "react";

export type ShotSample = {
  index: number;
  id: string;
  local: number;
};

export type LandingTimeline = MutableRefObject<ShotSample>;

