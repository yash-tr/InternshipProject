# Dockerfile for Rails Backend
# Multi-stage build for production optimization

# Stage 1: Build dependencies
FROM ruby:3.2.0-slim AS builder

# Install build dependencies
RUN apt-get update -qq && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install gems
COPY Gemfile Gemfile.lock ./
RUN bundle install --without development test

# Stage 2: Production image
FROM ruby:3.2.0-slim

# Install runtime dependencies
RUN apt-get update -qq && apt-get install -y \
    libpq-dev \
    curl \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 app

# Set working directory
WORKDIR /app

# Copy gems from builder
COPY --from=builder /usr/local/bundle /usr/local/bundle

# Copy application files
COPY --chown=app:app . .

# Switch to app user
USER app

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:3000/health || exit 1

# Start application
CMD ["bundle", "exec", "rails", "server", "-b", "0.0.0.0"]

