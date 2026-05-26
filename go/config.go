package vectorless

import "os"

// TransportProtocol selects the wire protocol.
type TransportProtocol string

const (
	// TransportHTTP uses standard REST/JSON endpoints (default).
	TransportHTTP TransportProtocol = "http"
	// TransportConnect uses ConnectRPC JSON protocol.
	TransportConnect TransportProtocol = "connect"
)

// Config holds the resolved SDK configuration.
type Config struct {
	// APIKey for Bearer token authentication. Optional for self-hosted.
	APIKey string
	// BaseURL of the Vectorless server (default "http://localhost:8080").
	BaseURL string
	// Store scopes every request to one store (sent as X-Vectorless-Store).
	// Only needed for org-wide keys; a store-bound key scopes automatically.
	Store string
	// Transport protocol (default TransportHTTP).
	Transport TransportProtocol
	// TimeoutMs is the request timeout in milliseconds (default 30,000).
	TimeoutMs int64
	// MaxRetries is the max retry attempts for transient errors (default 3).
	MaxRetries int
	// RetryDelayMs is the base delay between retries in ms (default 500).
	RetryDelayMs int64
}

// Option is a functional option for configuring the client.
type Option func(*Config)

// WithAPIKey sets the API key for authentication.
func WithAPIKey(key string) Option {
	return func(c *Config) { c.APIKey = key }
}

// WithBaseURL sets the server base URL.
func WithBaseURL(url string) Option {
	return func(c *Config) { c.BaseURL = url }
}

// WithStore scopes every request to one store (X-Vectorless-Store).
func WithStore(store string) Option {
	return func(c *Config) { c.Store = store }
}

// WithTransport selects the wire protocol.
func WithTransport(t TransportProtocol) Option {
	return func(c *Config) { c.Transport = t }
}

// WithTimeout sets the request timeout in milliseconds.
func WithTimeout(ms int64) Option {
	return func(c *Config) { c.TimeoutMs = ms }
}

// WithMaxRetries sets the max retry attempts.
func WithMaxRetries(n int) Option {
	return func(c *Config) { c.MaxRetries = n }
}

// WithRetryDelay sets the base retry delay in milliseconds.
func WithRetryDelay(ms int64) Option {
	return func(c *Config) { c.RetryDelayMs = ms }
}

func resolveConfig(opts []Option) Config {
	cfg := Config{
		BaseURL:      "http://localhost:8080",
		Transport:    TransportHTTP,
		TimeoutMs:    30_000,
		MaxRetries:   3,
		RetryDelayMs: 500,
	}

	for _, opt := range opts {
		opt(&cfg)
	}

	// Fallback to env var for API key.
	if cfg.APIKey == "" {
		cfg.APIKey = os.Getenv("VECTORLESS_API_KEY")
	}
	if cfg.BaseURL == "http://localhost:8080" {
		if envURL := os.Getenv("VECTORLESS_BASE_URL"); envURL != "" {
			cfg.BaseURL = envURL
		}
	}

	return cfg
}
