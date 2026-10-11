import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error caught by ErrorBoundary:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#F7F5F0] text-[#252821] flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white border border-[#E7E4DC] rounded-2xl p-6 shadow-dropdown text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-[#FEF8ED] border border-[#FCE6BE] text-[#A66A12] mx-auto flex items-center justify-center">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h2 className="text-base font-semibold text-[#252821]">Something went wrong</h2>
            <p className="text-xs text-[#74766F] leading-relaxed">
              {this.state.error?.message || 'An unexpected rendering error occurred.'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-[#4263EB] hover:bg-[#3451D1] text-white text-xs font-semibold shadow-sm transition"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reload Application</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
