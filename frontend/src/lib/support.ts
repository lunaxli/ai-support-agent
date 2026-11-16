export type Status =
  | "open"
  | "in_progress"
  | "waiting_review"
  | "resolved"
  | "closed"

export const statusLabel: Record<Status, string> = {
  open: "待处理",
  in_progress: "处理中",
  waiting_review: "待审核",
  resolved: "已解决",
  closed: "已关闭",
}

export type Ticket = {
  id: string
  owner_id: string
  subject: string
  description: string
  status: Status
  version: number
  created_at: string
}

export type Analysis = {
  id: string
  provider: "mock" | "deepseek"
  category: string | null
  priority: string | null
  summary: string | null
  risk_flags: string[]
  route: "draft_ready" | "human_review"
  reason: string | null
  draft: string | null
  created_at: string
  sources: {
    passage_id: string
    title: string
    path: string
    excerpt: string
  }[]
}

export type TicketDetail = Ticket & {
  final_reply: string | null
  analyses: Analysis[]
  reviews: {
    analysis_id: string
    decision: "approved" | "rejected"
    note: string
    final_reply: string | null
  }[]
  logs: {
    action: string
    actor_id: string | null
    details: Record<string, unknown>
    created_at: string
  }[]
}

export type Capabilities = { can_review: boolean; ai_mode: "mock" | "deepseek" }

export async function supportRequest<T>(
  path: string,
  method = "GET",
  data?: object,
): Promise<T> {
  const base = import.meta.env.VITE_API_URL ?? ""
  const response = await fetch(`${base}/api/v1/tickets/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
      ...(data ? { "Content-Type": "application/json" } : {}),
    },
    body: data ? JSON.stringify(data) : undefined,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    if (
      response.status === 401 ||
      body?.detail === "Could not validate credentials"
    ) {
      localStorage.removeItem("access_token")
      window.location.assign("/login")
    }
    throw new Error(
      Array.isArray(body?.detail)
        ? body.detail.map((item: { msg: string }) => item.msg).join("；")
        : body?.detail || `请求失败（${response.status}）`,
    )
  }
  return response.status === 204 ? (undefined as T) : response.json()
}
