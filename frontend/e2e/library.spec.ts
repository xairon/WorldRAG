import { test, expect } from "./fixtures"

test.describe("Library", () => {
  test("shows library page with heading", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
  })

  test("shows upload card", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    await expect(page.getByText(/add a book|drop your first book/i)).toBeVisible()
  })

  test("shows book count", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    await expect(page.getByText(/\d+ books?/)).toBeVisible()
  })
})
