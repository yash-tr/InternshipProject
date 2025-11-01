import React from 'react';
import styled from 'styled-components';

const ErrorContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 20px;
  text-align: center;
`;

const ErrorTitle = styled.h1`
  font-size: 48px;
  color: #e74c3c;
  margin-bottom: 16px;
`;

const ErrorMessage = styled.p`
  font-size: 18px;
  color: #666;
  margin-bottom: 24px;
`;

const RetryButton = styled.button`
  background: #3498db;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  
  &:hover {
    background: #2980b9;
  }
`;

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log to error tracking service
    console.error('Error caught by boundary:', error, errorInfo);
    
    // Send to Sentry or similar
    if (window.Sentry) {
      window.Sentry.captureException(error, {
        contexts: { react: errorInfo }
      });
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <ErrorContainer>
          <ErrorTitle>😕 Oops! Something went wrong</ErrorTitle>
          <ErrorMessage>
            We're sorry for the inconvenience. An unexpected error occurred.
          </ErrorMessage>
          {this.props.fallback || (
            <>
              <p style={{ color: '#999', fontSize: '14px', marginBottom: '24px' }}>
                {process.env.NODE_ENV === 'development' && this.state.error?.toString()}
              </p>
              <RetryButton onClick={this.handleRetry}>
                Retry
              </RetryButton>
            </>
          )}
        </ErrorContainer>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

