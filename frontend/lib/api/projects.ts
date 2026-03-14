import { apiFetch } from "./client"

export interface Project {
  id: string
  slug: string
  name: string
  description: string
  cover_image: string | null
  created_at: string
  updated_at: string
  books_count: number
  has_profile: boolean
  entity_count: number
}

export interface ProjectListResponse {
  projects: Project[]
  total: number
}

export function listProjects(): Promise<ProjectListResponse> {
  return apiFetch("/projects")
}

export function getProject(slug: string): Promise<Project> {
  return apiFetch(`/projects/${slug}`)
}

export function createProject(data: {
  slug: string
  name: string
  description?: string
}): Promise<Project> {
  return apiFetch("/projects", { method: "POST", body: JSON.stringify(data) })
}

export function deleteProject(slug: string): Promise<void> {
  return apiFetch(`/projects/${slug}`, { method: "DELETE" })
}

// H10: Return type matches what the backend actually returns (project_file row)
export function uploadBookToProject(
  slug: string,
  file: File,
  bookNum: number = 1,
): Promise<Record<string, unknown>> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("book_num", String(bookNum))
  return apiFetch(`/projects/${slug}/books`, { method: "POST", body: formData })
}

// H9: Removed bookId parameter — backend extracts per-project, not per-book
export function triggerExtraction(
  slug: string,
): Promise<{ job_id: string; mode: string }> {
  return apiFetch(`/projects/${slug}/extract`, { method: "POST" })
}

export function getProjectStats(slug: string): Promise<Record<string, unknown>> {
  return apiFetch(`/projects/${slug}/stats`)
}

export interface ProjectBook {
  id: string
  filename: string
  file_size: number
  book_id: string | null
  book_num: number
  uploaded_at: string
}

export function listProjectBooks(slug: string): Promise<ProjectBook[]> {
  return apiFetch(`/projects/${slug}/books`)
}
