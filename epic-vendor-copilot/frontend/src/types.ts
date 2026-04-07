export type SourceInfo = {
  id: string | null
  section: string | null
  question: string | null
  url: string | null
  confidence: number | null
}

export type ResponseType = "answer" | "clarification" | "domain_miss";

export type Message = {
  id: string
  role: "user" | "assistant"
  content: string
  source: SourceInfo | null
  memoryUsed: boolean
  memoryTurnRefs: number[]
  responseType: ResponseType
  timestamp: number
  streaming?: boolean
  tokenBudgetUsed?: number
  mode?: string
}
