import { test, expect } from "./fixtures"

test.describe("Dashboard", () => {
  test("shows WorldRAG header", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByText("WorldRAG")).toBeVisible()
  })

  test("shows new project button", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByRole("button", { name: /new project|create/i })).toBeVisible()
  })

  test("create project flow", async ({ page }) => {
    await page.goto("/")
    await page.getByRole("button", { name: /new project|create/i }).click()
    await expect(page.getByPlaceholder(/project name/i)).toBeVisible()
  })

  test("shows empty state or project cards", async ({ page }) => {
    await page.goto("/")
    const hasProjects = await page.locator("a[href*='/projects/']").count() > 0
    if (hasProjects) {
      await expect(page.locator("a[href*='/projects/']").first()).toBeVisible()
    } else {
      await expect(page.getByText(/create your first universe/i)).toBeVisible()
    }
  })
})
