import { expect, type Page, test } from "@playwright/test"

async function login(page: Page, email: string, password: string) {
  await page.goto("/login", { waitUntil: "domcontentloaded" })
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByRole("button", { name: "Log In" }).click()
  await page.waitForURL("/")
}

async function logout(page: Page) {
  await page.getByTestId("user-menu").click()
  await page.getByRole("menuitem", { name: "Log out" }).click()
  await page.waitForURL("/login")
}

test("staff approves a cited ticket draft", async ({ page }) => {
  await page.goto("/tickets")
  await expect(page.getByRole("heading", { name: "工单中心" })).toBeVisible()
  await page.getByRole("button", { name: "新建工单" }).click()
  const subject = `重置登录密码 ${Date.now()}`
  await page.getByLabel("标题", { exact: true }).fill(subject)
  await page.getByLabel("问题描述").fill("忘记登录密码，如何重置？")
  await page.getByRole("button", { name: "提交工单" }).click()
  await expect(page.getByRole("heading", { name: subject })).toBeVisible()
  await page.getByRole("button", { name: "运行 AI 分析" }).click()
  await expect(page.getByText("草稿就绪")).toBeVisible()
  await expect(page.getByText(/account\.md#1/)).toBeVisible()
  await page.getByLabel("处理备注").fill("已核对密码重置步骤")
  await page.getByRole("button", { name: "批准回复" }).click()
  await expect(page.getByRole("heading", { name: "最终回复" })).toBeVisible()
  await expect(page.getByText("完成审核")).toBeVisible()
  await page.reload()
  await page.getByRole("button", { name: new RegExp(subject) }).click()
  await expect(page.getByRole("heading", { name: "最终回复" })).toBeVisible()
})

test("customer and agent handle a risk ticket", async ({
  page,
  request,
  baseURL,
}) => {
  test.setTimeout(60_000)
  const api = process.env.VITE_API_URL || baseURL
  const password = "SupportBrowserTest2026"
  const suffix = Date.now()
  const customer = `customer-${suffix}@example.com`
  const agent = `agent-${suffix}@example.com`
  const customerAccount = await request.post(`${api}/api/v1/users/signup`, {
    data: { email: customer, password },
  })
  const agentAccount = await request.post(`${api}/api/v1/users/signup`, {
    data: { email: agent, password },
  })
  expect(customerAccount.ok()).toBeTruthy()
  expect(agentAccount.ok()).toBeTruthy()

  await page.goto("/")
  const adminToken = await page.evaluate(() =>
    localStorage.getItem("access_token"),
  )
  const grant = await request.put(
    `${api}/api/v1/tickets/staff/${(await agentAccount.json()).id}`,
    {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { is_support_agent: true },
    },
  )
  expect(grant.ok()).toBeTruthy()

  await logout(page)
  await login(page, customer, password)
  await page.goto("/tickets")
  await expect(page.getByText(/我的工单/)).toBeVisible()
  await page.getByRole("button", { name: "新建工单" }).click()
  const subject = `退款申请 ${suffix}`
  await page.getByLabel("标题", { exact: true }).fill(subject)
  await page.getByLabel("问题描述").fill("账单重复扣款，请退款")
  await page.getByRole("button", { name: "提交工单" }).click()
  await expect(page.getByRole("heading", { name: subject })).toBeVisible()
  await expect(page.getByRole("button", { name: "运行 AI 分析" })).toHaveCount(
    0,
  )

  await logout(page)
  await login(page, agent, password)
  await page.goto("/tickets")
  await expect(page.getByText(/客服工作台/)).toBeVisible()
  await page.getByRole("button", { name: new RegExp(subject) }).click()
  await page.getByRole("button", { name: "运行 AI 分析" }).click()
  await expect(page.getByText(/命中风险规则/)).toBeVisible()
  await page.getByLabel("处理备注").fill("先核对账单明细")
  await page.getByRole("button", { name: "驳回分析" }).click()
  await expect(page.getByText("已驳回")).toBeVisible()
  await page.getByRole("button", { name: "运行 AI 分析" }).click()
  const manualReply = "客服将继续核对相关账单记录。"
  await page.getByLabel("人工回复（批准时必填）").fill(manualReply)
  await page.getByLabel("处理备注").fill("账单已检查")
  await page.getByRole("button", { name: "批准回复" }).click()
  await expect(page.getByRole("heading", { name: "最终回复" })).toBeVisible()

  await logout(page)
  await login(page, customer, password)
  await page.goto("/tickets")
  await page.getByRole("button", { name: new RegExp(subject) }).click()
  await expect(page.getByText(manualReply)).toBeVisible()
  await expect(page.getByRole("heading", { name: "分析记录" })).toHaveCount(0)
})
