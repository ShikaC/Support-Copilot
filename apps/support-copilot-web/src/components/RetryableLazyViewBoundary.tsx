import { Component, type ReactNode } from 'react'
import { Button } from 'antd'

type RetryableLazyViewBoundaryProps = {
  readonly children: ReactNode
  readonly onRetry: () => void
}

type RetryableLazyViewBoundaryState = {
  readonly error: Error | null
}

class LazyViewLoadError extends Error {
  readonly name = 'LazyViewLoadError'
  readonly cause: unknown

  constructor(cause: unknown) {
    super('The requested view could not be loaded.')
    this.cause = cause
  }
}

export class RetryableLazyViewBoundary extends Component<RetryableLazyViewBoundaryProps, RetryableLazyViewBoundaryState> {
  readonly state: RetryableLazyViewBoundaryState = { error: null }

  static getDerivedStateFromError(error: unknown): RetryableLazyViewBoundaryState {
    return { error: error instanceof Error ? error : new LazyViewLoadError(error) }
  }

  private readonly retry = () => {
    this.setState({ error: null })
    this.props.onRetry()
  }

  render() {
    if (this.state.error !== null) {
      return <div className="view-enter"><section className="knowledge-panel data-loading" role="alert">
        <span>页面资源加载失败，请重试。</span>
        <Button type="primary" onClick={this.retry}>重试加载</Button>
      </section></div>
    }
    return this.props.children
  }
}
