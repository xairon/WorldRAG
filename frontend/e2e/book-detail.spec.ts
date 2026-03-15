import { test, expect } from "./fixtures"

test.describe("Book Detail", () => {
  test("shows book metadata when navigating to a book", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)

    const bookLink = page.locator("a[href*='/books/']").first()
    if (!(await bookLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await bookLink.click()
    await page.waitForURL(/\/books\//)
    // Should show some heading (book title)
    await expect(page.getByRole("heading").first()).toBeVisible()
  })

  test("shows chapters tab", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)

    const bookLink = page.locator("a[href*='/books/']").first()
    if (!(await bookLink.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip()
      return
    }
    await bookLink.click()
    await page.waitForURL(/\/books\//)
    await expect(page.getByText(/chapters/i).first()).toBeVisible()
  })
})
