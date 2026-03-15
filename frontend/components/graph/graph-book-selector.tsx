"use client"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

interface BookOption {
  id: string
  title: string
}

interface GraphBookSelectorProps {
  books: BookOption[]
  selected: string
  onSelect: (bookId: string) => void
}

export function GraphBookSelector({ books, selected, onSelect }: GraphBookSelectorProps) {
  // Hide if only one book
  if (books.length <= 1) return null

  return (
    <Select value={selected} onValueChange={onSelect}>
      <SelectTrigger size="sm" className="w-56 bg-background/80 backdrop-blur-sm border-border/50">
        <SelectValue placeholder="Select book" />
      </SelectTrigger>
      <SelectContent>
        {books.map((book) => (
          <SelectItem key={book.id} value={book.id}>
            {book.title}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
