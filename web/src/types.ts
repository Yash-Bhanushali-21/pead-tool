export type Role = "user" | "assistant";

export interface ChatTurn {
  role: Role;
  content: string;
  id: string;
}

export type StreamEvent =
  | { type: "text_delta"; content: string }
  | { type: "thinking_delta"; content: string }
  | { type: "tool_call"; tool_name: string; args: unknown; tool_call_id?: string | null }
  | { type: "tool_result"; tool_call_id?: string | null; content_preview: string }
  | { type: "done"; output: string }
  | { type: "error"; message: string }
  | { type: string; [k: string]: unknown };
