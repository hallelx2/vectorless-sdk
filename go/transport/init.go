package transport

import vectorless "github.com/hallelx2/vectorless-sdk/go"

func init() {
	vectorless.RegisterTransportFactory(vectorless.TransportHTTP, func(cfg vectorless.Config) vectorless.TransportIface {
		return NewHTTPTransport(cfg)
	})
	vectorless.RegisterTransportFactory(vectorless.TransportConnect, func(cfg vectorless.Config) vectorless.TransportIface {
		return NewConnectTransport(cfg)
	})
}
