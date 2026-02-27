"use client"

import { Component } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface Props {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <AlertTriangle className="h-10 w-10 text-amber-400" />
          <div className="text-center">
            <p className="text-sm font-medium text-slate-300 mb-1">Something went wrong</p>
            <p className="text-xs text-slate-500 max-w-md">
              {this.state.error?.message ?? "An unexpected error occurred"}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            <RefreshCw className="h-3 w-3 mr-2" />
            Try again
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
