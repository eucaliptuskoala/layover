import { Component, type PropsWithChildren } from 'react';

export class ErrorBoundary extends Component<PropsWithChildren, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="recovery-page">
          <div className="card p-8">
            <h1 className="text-xl font-bold">The sandbox could not render</h1>
            <p className="mt-3 text-muted">
              Any submitted workflow may still be running. Reloading will not resubmit it.
            </p>
            <a className="btn btn-primary mt-6" href="/checkout">
              Return to checkout
            </a>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
