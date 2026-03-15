import { test as base, expect } from "@playwright/test"
import path from "path"

export const EPUB_PATH = path.resolve(__dirname, "../../tests/fixtures/primal-hunter.epub")

export const test = base.extend({})
export { expect }
