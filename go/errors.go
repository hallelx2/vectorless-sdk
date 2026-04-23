package vectorless

import "fmt"

// Error is the base error type for all Vectorless SDK errors.
type Error struct {
	Message   string
	Status    int
	Code      string
	RequestID string
}

func (e *Error) Error() string {
	if e.RequestID != "" {
		return fmt.Sprintf("vectorless: %s (status=%d, code=%s, request_id=%s)", e.Message, e.Status, e.Code, e.RequestID)
	}
	return fmt.Sprintf("vectorless: %s (status=%d, code=%s)", e.Message, e.Status, e.Code)
}

// Typed error constructors — callers can use errors.As to check the type,
// or switch on the Status field.

func newAuthenticationError(message, requestID string) *Error {
	return &Error{Message: message, Status: 401, Code: "authentication_error", RequestID: requestID}
}

func newPermissionDeniedError(message, requestID string) *Error {
	return &Error{Message: message, Status: 403, Code: "permission_denied", RequestID: requestID}
}

func newNotFoundError(message, requestID string) *Error {
	return &Error{Message: message, Status: 404, Code: "not_found", RequestID: requestID}
}

func newValidationError(message, requestID string) *Error {
	return &Error{Message: message, Status: 400, Code: "validation_error", RequestID: requestID}
}

func newConflictError(message, requestID string) *Error {
	return &Error{Message: message, Status: 409, Code: "conflict", RequestID: requestID}
}

func newRateLimitError(message, requestID string) *Error {
	return &Error{Message: message, Status: 429, Code: "rate_limit_exceeded", RequestID: requestID}
}

func newTimeoutError(message, requestID string) *Error {
	return &Error{Message: message, Status: 408, Code: "timeout", RequestID: requestID}
}

func newServerError(message, requestID string) *Error {
	return &Error{Message: message, Status: 500, Code: "server_error", RequestID: requestID}
}

func newDocumentFailedError(message, requestID string) *Error {
	return &Error{Message: message, Status: 422, Code: "document_failed", RequestID: requestID}
}

func newStreamError(message, requestID string) *Error {
	return &Error{Message: message, Status: 0, Code: "stream_error", RequestID: requestID}
}

// IsNotFound returns true if the error is a 404 Not Found.
func IsNotFound(err error) bool {
	if e, ok := err.(*Error); ok {
		return e.Status == 404
	}
	return false
}

// IsAuthError returns true if the error is a 401 or 403.
func IsAuthError(err error) bool {
	if e, ok := err.(*Error); ok {
		return e.Status == 401 || e.Status == 403
	}
	return false
}

// IsRateLimited returns true if the error is a 429 rate limit.
func IsRateLimited(err error) bool {
	if e, ok := err.(*Error); ok {
		return e.Status == 429
	}
	return false
}

// IsRetryable returns true if the error is transient and the request can be retried.
func IsRetryable(err error) bool {
	if e, ok := err.(*Error); ok {
		return e.Status == 429 || e.Status == 408 || e.Status == 504 || e.Status >= 500
	}
	return false
}
