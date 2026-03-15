import { test, expect } from "./fixtures"

test.describe("Navigation", () => {
  test("navigate to project workspace", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    // Should see Library heading
    await expect(page.getByText("Library")).toBeVisible()
  })

  test("sidebar shows on desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 900 })
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    await expect(page.locator("aside")).toBeVisible()
  })

  test("back to dashboard from sidebar", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    await page.locator('a[title="All projects"]').click()
    await expect(page).toHaveURL("/")
  })
})
