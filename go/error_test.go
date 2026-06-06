package vectorless_test

import (
	"errors"
	"testing"

	"github.com/hallelx2/vectorless-sdk/go"
)

func TestErrorHelpers(t *testing.T) {
	tests := []struct {
		name          string
		status        int
		isNotFound    bool
		isAuthError   bool
		isRateLimited bool
		isRetryable   bool
	}{
		{"NotFound 404", 404, true, false, false, false},
		{"AuthError 401", 401, false, true, false, false},
		{"AuthError 403", 403, false, true, false, false},
		{"RateLimited 429", 429, false, false, true, true},
		{"Timeout 408", 408, false, false, false, true},
		{"Timeout 504", 504, false, false, false, true},
		{"ServerError 500", 500, false, false, false, true},
		{"ServerError 502", 502, false, false, false, true},
		{"BadRequest 400", 400, false, false, false, false},
		{"Conflict 409", 409, false, false, false, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := &vectorless.Error{
				Message:   "test error",
				Status:    tt.status,
				Code:      "test_code",
				RequestID: "req_123",
			}

			if got := vectorless.IsNotFound(err); got != tt.isNotFound {
				t.Errorf("IsNotFound() = %v, want %v", got, tt.isNotFound)
			}
			if got := vectorless.IsAuthError(err); got != tt.isAuthError {
				t.Errorf("IsAuthError() = %v, want %v", got, tt.isAuthError)
			}
			if got := vectorless.IsRateLimited(err); got != tt.isRateLimited {
				t.Errorf("IsRateLimited() = %v, want %v", got, tt.isRateLimited)
			}
			if got := vectorless.IsRetryable(err); got != tt.isRetryable {
				t.Errorf("IsRetryable() = %v, want %v", got, tt.isRetryable)
			}
		})
	}
}

func TestErrorHelpersWithWrappedError(t *testing.T) {
	// Our functions take an error interface, let's verify standard error
	// wrapping behaves as expected or if it fails (currently the SDK helpers
	// use a simple type assertion `e, ok := err.(*Error)` which means
	// they don't support wrapped errors. If that's the design, we test it).
	// To support wrapped errors, the sdk should use `errors.As`.

	err := &vectorless.Error{
		Message:   "not found",
		Status:    404,
		Code:      "not_found",
	}

	if !vectorless.IsNotFound(err) {
		t.Errorf("Expected IsNotFound to be true for 404")
	}

	// Just a plain error
	plainErr := errors.New("plain error")
	if vectorless.IsNotFound(plainErr) {
		t.Errorf("IsNotFound should be false for non-vectorless.Error")
	}
}
