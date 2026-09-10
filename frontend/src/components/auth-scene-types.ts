import type { MutableRefObject } from "react";

export type AuthVisualState = "idle" | "typing" | "error" | "success";

export type AuthSceneSignals = {
  pointer: MutableRefObject<{ x: number; y: number }>;
  lastInputAt: MutableRefObject<number>;
};
