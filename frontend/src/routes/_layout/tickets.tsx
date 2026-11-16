import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ClipboardList, Plus } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import useAuth from "@/hooks/useAuth"
import {
  type Analysis,
  type Capabilities,
  type Status,
  type Ticket,
  type TicketDetail,
  statusLabel,
  supportRequest,
} from "@/lib/support"

export const Route = createFileRoute("/_layout/tickets")({
  component: Tickets,
  head: () => ({ meta: [{ title: "工单中心 · AI Support Agent" }] }),
})

const selectClass = "h-9 rounded-md border bg-background px-3 text-sm"
const textareaClass =
  "min-h-24 w-full rounded-md border bg-background p-3 text-sm"
const pageSize = 20

function Tickets() {
  const { user } = useAuth()
  const cache = useQueryClient()
  const [filter, setFilter] = useState("")
  const [page, setPage] = useState(0)
  const [ticketId, setTicketId] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const capabilities = useQuery({
    queryKey: ["support", user?.id, "capabilities"],
    queryFn: () => supportRequest<Capabilities>("capabilities"),
    enabled: !!user,
  })
  const tickets = useQuery({
    queryKey: ["support", user?.id, "list", filter, page],
    queryFn: () =>
      supportRequest<{ data: Ticket[]; count: number }>(
        `?offset=${page * pageSize}&limit=${pageSize}${filter ? `&status=${filter}` : ""}`,
      ),
    enabled: !!user,
  })
  const detail = useQuery({
    queryKey: ["support", user?.id, "detail", ticketId],
    queryFn: () => supportRequest<TicketDetail>(String(ticketId)),
    enabled: !!user && !!ticketId && !creating,
  })
  const refresh = () =>
    cache.invalidateQueries({ queryKey: ["support", user?.id] })

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">工单中心</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {capabilities.data?.can_review ? "客服工作台" : "我的工单"}
            {capabilities.data &&
              ` · ${capabilities.data.ai_mode === "mock" ? "Mock 演示" : "DeepSeek"}`}
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus size={16} />
          新建工单
        </Button>
      </header>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,1.5fr)]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-2">
            <CardTitle>
              <h2>工单列表</h2>
            </CardTitle>
            <select
              aria-label="按状态筛选"
              className={selectClass}
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value)
                setPage(0)
              }}
            >
              <option value="">全部状态</option>
              {Object.entries(statusLabel).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </CardHeader>
          <CardContent className="space-y-2">
            {(tickets.error || capabilities.error) && (
              <ErrorText error={tickets.error || capabilities.error} />
            )}
            {tickets.isPending && (
              <p className="text-sm text-muted-foreground">加载中…</p>
            )}
            {tickets.data?.data.length === 0 && (
              <p className="text-sm text-muted-foreground">
                暂无符合条件的工单。
              </p>
            )}
            {tickets.data?.data.map((ticket) => (
              <button
                key={ticket.id}
                type="button"
                aria-pressed={!creating && ticket.id === ticketId}
                onClick={() => {
                  setTicketId(ticket.id)
                  setCreating(false)
                }}
                className="flex w-full items-center justify-between gap-2 rounded-md border p-3 text-left hover:bg-accent aria-pressed:bg-accent"
              >
                <span className="min-w-0 truncate text-sm font-medium">
                  {ticket.subject}
                </span>
                <Badge variant="secondary">{statusLabel[ticket.status]}</Badge>
              </button>
            ))}
            {!!tickets.data && (tickets.data.count > pageSize || page > 0) && (
              <div className="flex items-center justify-between pt-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 0}
                  onClick={() => setPage(page - 1)}
                >
                  上一页
                </Button>
                <span className="text-xs text-muted-foreground">
                  第 {page + 1} 页
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={(page + 1) * pageSize >= tickets.data.count}
                  onClick={() => setPage(page + 1)}
                >
                  下一页
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {creating ? (
          <Card>
            <CardHeader>
              <CardTitle>
                <h2>新建工单</h2>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <TicketForm
                save={async (subject, description) => {
                  const ticket = await supportRequest<Ticket>("", "POST", {
                    subject,
                    description,
                  })
                  setCreating(false)
                  setTicketId(ticket.id)
                  setFilter("")
                  setPage(0)
                  await refresh()
                }}
              />
            </CardContent>
          </Card>
        ) : detail.data ? (
          <Details
            key={detail.data.id}
            ticket={detail.data}
            staff={capabilities.data?.can_review ?? false}
            refresh={refresh}
            onDelete={() => {
              setTicketId(null)
              setPage(0)
            }}
          />
        ) : (
          <Card>
            <CardContent className="flex min-h-48 flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
              <ClipboardList size={28} />
              {detail.error ? (
                <ErrorText error={detail.error} />
              ) : ticketId ? (
                "加载工单…"
              ) : (
                "选择一张工单查看详情"
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  )
}

function ErrorText({ error }: { error: Error | null }) {
  return (
    error && (
      <p role="alert" className="text-sm text-destructive">
        {error.message}
      </p>
    )
  )
}

function TicketForm({
  ticket,
  save,
  cancel,
}: {
  ticket?: Ticket
  save: (subject: string, description: string) => Promise<void>
  cancel?: () => void
}) {
  const [subject, setSubject] = useState(ticket?.subject ?? "")
  const [description, setDescription] = useState(ticket?.description ?? "")
  const submit = useMutation({ mutationFn: () => save(subject, description) })
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        submit.mutate()
      }}
    >
      <div className="space-y-2">
        <Label htmlFor="subject">标题</Label>
        <Input
          id="subject"
          required
          maxLength={160}
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="description">问题描述</Label>
        <textarea
          className={textareaClass}
          id="description"
          required
          maxLength={6000}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </div>
      <ErrorText error={submit.error} />
      <div className="flex gap-2">
        <Button
          disabled={submit.isPending || !subject.trim() || !description.trim()}
          type="submit"
        >
          {ticket ? "保存修改" : "提交工单"}
        </Button>
        {cancel && (
          <Button type="button" variant="ghost" onClick={cancel}>
            取消
          </Button>
        )}
      </div>
    </form>
  )
}

function Details({
  ticket,
  staff,
  refresh,
  onDelete,
}: {
  ticket: TicketDetail
  staff: boolean
  refresh: () => Promise<void>
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [note, setNote] = useState("")
  const [reply, setReply] = useState("")
  const latest = ticket.analyses[ticket.analyses.length - 1]
  const change = useMutation({
    mutationFn: async ({
      path,
      method,
      body,
    }: {
      path: string
      method: string
      body?: object
    }) => supportRequest(`${ticket.id}${path}`, method, body),
    onSuccess: async (_result, variables) => {
      if (variables.method === "DELETE") onDelete()
      setConfirmDelete(false)
      setNote("")
      setReply("")
      await refresh()
    },
    onError: refresh,
  })
  const transition = (status: Status) =>
    change.mutate({
      path: "/status",
      method: "PATCH",
      body: { version: ticket.version, status, note: note.trim() || null },
    })
  const review = (decision: "approved" | "rejected") => {
    if (!latest) return
    change.mutate({
      path: "/reviews",
      method: "POST",
      body: {
        version: ticket.version,
        analysis_id: latest.id,
        decision,
        note,
        final_reply: decision === "approved" ? reply.trim() || null : null,
      },
    })
  }

  return (
    <section className="min-w-0 space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="break-all text-xl">
              <h2>{ticket.subject}</h2>
            </CardTitle>
            <Badge>{statusLabel[ticket.status]}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {editing ? (
            <TicketForm
              ticket={ticket}
              cancel={() => setEditing(false)}
              save={async (subject, description) => {
                await supportRequest(ticket.id, "PUT", {
                  subject,
                  description,
                  version: ticket.version,
                })
                setEditing(false)
                await refresh()
              }}
            />
          ) : (
            <p className="whitespace-pre-wrap break-words text-sm">
              {ticket.description}
            </p>
          )}
          {ticket.final_reply && (
            <div className="rounded-md border bg-muted/40 p-4">
              <h2 className="text-sm font-semibold">最终回复</h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-sm">
                {ticket.final_reply}
              </p>
            </div>
          )}
          {ticket.status === "open" && !editing && (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditing(true)}
              >
                编辑工单
              </Button>
              {confirmDelete ? (
                <>
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={change.isPending}
                    onClick={() =>
                      change.mutate({
                        path: `?version=${ticket.version}`,
                        method: "DELETE",
                      })
                    }
                  >
                    确认删除
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setConfirmDelete(false)}
                  >
                    取消删除
                  </Button>
                </>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setConfirmDelete(true)}
                >
                  删除工单
                </Button>
              )}
            </div>
          )}
          {staff && (
            <>
              {(ticket.status === "in_progress" ||
                ticket.status === "waiting_review") && (
                <div className="space-y-2">
                  <Label htmlFor="review-note">处理备注</Label>
                  <Input
                    id="review-note"
                    maxLength={1000}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                </div>
              )}
              {ticket.status === "waiting_review" && latest && (
                <div className="space-y-2">
                  <Label htmlFor="final-reply">
                    {latest.draft
                      ? "修改最终回复（可选）"
                      : "人工回复（批准时必填）"}
                  </Label>
                  <textarea
                    id="final-reply"
                    className={textareaClass}
                    maxLength={4000}
                    value={reply}
                    onChange={(event) => setReply(event.target.value)}
                  />
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {["open", "in_progress"].includes(ticket.status) && (
                  <Button
                    disabled={change.isPending}
                    onClick={() =>
                      change.mutate({
                        path: `/analyses?version=${ticket.version}`,
                        method: "POST",
                      })
                    }
                  >
                    {change.isPending ? "处理中…" : "运行 AI 分析"}
                  </Button>
                )}
                {ticket.status === "open" && (
                  <Button
                    variant="outline"
                    disabled={change.isPending}
                    onClick={() => transition("in_progress")}
                  >
                    开始处理
                  </Button>
                )}
                {ticket.status === "in_progress" && (
                  <Button
                    variant="outline"
                    disabled={change.isPending || !note.trim()}
                    onClick={() => transition("resolved")}
                  >
                    手动解决
                  </Button>
                )}
                {ticket.status === "waiting_review" && latest && (
                  <>
                    <Button
                      disabled={
                        change.isPending ||
                        !note.trim() ||
                        !(reply.trim() || latest.draft)
                      }
                      onClick={() => review("approved")}
                    >
                      批准回复
                    </Button>
                    <Button
                      variant="outline"
                      disabled={change.isPending || !note.trim()}
                      onClick={() => review("rejected")}
                    >
                      驳回分析
                    </Button>
                  </>
                )}
                {ticket.status === "resolved" && (
                  <Button
                    variant="outline"
                    disabled={change.isPending}
                    onClick={() => transition("closed")}
                  >
                    关闭工单
                  </Button>
                )}
              </div>
            </>
          )}
          <ErrorText error={change.error} />
        </CardContent>
      </Card>
      {staff && ticket.analyses.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>分析记录</h2>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {[...ticket.analyses].reverse().map((analysis) => (
              <AnalysisCard
                key={analysis.id}
                analysis={analysis}
                review={ticket.reviews.find(
                  (entry) => entry.analysis_id === analysis.id,
                )}
              />
            ))}
          </CardContent>
        </Card>
      )}
      {staff && ticket.logs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>操作记录</h2>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2 text-sm">
              {ticket.logs.map((log, index) => (
                <li
                  key={index}
                  className="flex flex-wrap justify-between gap-2"
                >
                  <span>{logNames[log.action] || log.action}</span>
                  <time
                    className="text-muted-foreground"
                    dateTime={log.created_at}
                  >
                    {new Date(log.created_at).toLocaleString()}
                  </time>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </section>
  )
}

const logNames: Record<string, string> = {
  ticket_created: "创建工单",
  ticket_edited: "编辑工单",
  analysis_recorded: "保存分析",
  review_recorded: "完成审核",
  status_changed: "变更状态",
}
const reasons: Record<string, string> = {
  risk: "命中风险规则",
  no_evidence: "未检索到证据",
  insufficient_evidence: "证据不足或引用无效",
  model_error: "模型调用或输出异常",
}
const categories: Record<string, string> = {
  account: "账户",
  billing: "账单",
  technical: "技术",
  security: "安全",
  other: "其他",
}
const priorities: Record<string, string> = {
  low: "低",
  normal: "普通",
  high: "高",
  urgent: "紧急",
}
const risks: Record<string, string> = {
  security: "账户安全",
  financial: "财务",
  privacy: "隐私",
  legal: "法律",
}

function AnalysisCard({
  analysis,
  review,
}: {
  analysis: Analysis
  review?: TicketDetail["reviews"][number]
}) {
  return (
    <article className="space-y-3 rounded-md border p-4 text-sm">
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">
          {analysis.provider === "mock" ? "Mock" : "DeepSeek"}
        </Badge>
        <Badge variant="secondary">
          {analysis.route === "draft_ready" ? "草稿就绪" : "转人工处理"}
        </Badge>
        {analysis.category && (
          <Badge variant="outline">{categories[analysis.category]}</Badge>
        )}
        {analysis.priority && (
          <Badge variant="outline">
            优先级：{priorities[analysis.priority]}
          </Badge>
        )}
        <time className="text-muted-foreground" dateTime={analysis.created_at}>
          {new Date(analysis.created_at).toLocaleString()}
        </time>
      </div>
      {analysis.reason && (
        <p>
          {reasons[analysis.reason] || analysis.reason}
          {analysis.risk_flags.length > 0 &&
            ` · ${analysis.risk_flags.map((risk) => risks[risk]).join("、")}`}
        </p>
      )}
      {analysis.summary && (
        <p className="break-words text-muted-foreground">{analysis.summary}</p>
      )}
      {analysis.draft && (
        <p className="whitespace-pre-wrap break-words">{analysis.draft}</p>
      )}
      {analysis.sources.map((source) => (
        <details key={source.passage_id} className="rounded-md bg-muted/60 p-3">
          <summary className="cursor-pointer">
            {source.title} · {source.passage_id}
          </summary>
          <p className="mt-2 whitespace-pre-wrap break-words">
            {source.excerpt}
          </p>
        </details>
      ))}
      {review && (
        <p className="break-words">
          <strong>
            {review.decision === "approved" ? "已批准" : "已驳回"}
          </strong>{" "}
          · {review.note}
        </p>
      )}
    </article>
  )
}
