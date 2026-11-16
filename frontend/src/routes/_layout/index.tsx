import { createFileRoute, Link } from "@tanstack/react-router"

import { buttonVariants } from "@/components/ui/button"

import useAuth from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [
      {
        title: "AI Support Agent",
      },
    ],
  }),
})

function Dashboard() {
  const { user: currentUser } = useAuth()

  return (
    <main className="mx-auto max-w-7xl">
      <h1 className="text-3xl font-semibold tracking-tight">
        AI Support Agent
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        欢迎，{currentUser?.full_name || currentUser?.email}
      </p>
      <Link className={buttonVariants({ className: "mt-5" })} to="/tickets">
        打开工单中心
      </Link>
    </main>
  )
}
