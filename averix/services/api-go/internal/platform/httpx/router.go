package httpx

import (
	"net/http"
	"strings"
)

// Middleware wraps a Handler, preserving the error-returning signature so a
// middleware can short-circuit by returning an error.
type Middleware func(Handler) Handler

// Router is a thin layer over http.ServeMux: it adds middleware groups and
// adapts the error-returning Handler signature. Go 1.22+ method and wildcard
// patterns do the routing, so there is no third-party router to keep current.
type Router struct {
	mux    *http.ServeMux
	prefix string
	chain  []Middleware
}

func NewRouter() *Router {
	r := &Router{mux: http.NewServeMux()}
	// An unmatched path answers in the API's own envelope. Without this, Go's
	// ServeMux writes a plain-text "404 page not found", so a client that
	// mistypes a path gets a body in a different shape from every other error
	// — which is exactly the kind of inconsistency an API client cannot code
	// against.
	r.mux.HandleFunc("/", func(w http.ResponseWriter, req *http.Request) {
		WriteError(w, req, NotFoundf("no route for %s %s", req.Method, req.URL.Path))
	})
	return r
}

// Group returns a router that prefixes paths and appends middleware. The parent
// is unchanged, so groups compose without leaking middleware sideways.
func (r *Router) Group(prefix string, mw ...Middleware) *Router {
	chain := make([]Middleware, 0, len(r.chain)+len(mw))
	chain = append(chain, r.chain...)
	chain = append(chain, mw...)
	return &Router{
		mux:    r.mux,
		prefix: strings.TrimRight(r.prefix+prefix, "/"),
		chain:  chain,
	}
}

// Use appends middleware to this router in place.
func (r *Router) Use(mw ...Middleware) { r.chain = append(r.chain, mw...) }

func (r *Router) Handle(method, pattern string, h Handler) {
	wrapped := h
	// Applied in reverse so the first middleware registered is the outermost.
	for i := len(r.chain) - 1; i >= 0; i-- {
		wrapped = r.chain[i](wrapped)
	}
	full := method + " " + r.prefix + pattern
	r.mux.HandleFunc(full, func(w http.ResponseWriter, req *http.Request) {
		if err := wrapped(w, req); err != nil {
			WriteError(w, req, err)
		}
	})
}

func (r *Router) GET(p string, h Handler)    { r.Handle(http.MethodGet, p, h) }
func (r *Router) POST(p string, h Handler)   { r.Handle(http.MethodPost, p, h) }
func (r *Router) PUT(p string, h Handler)    { r.Handle(http.MethodPut, p, h) }
func (r *Router) PATCH(p string, h Handler)  { r.Handle(http.MethodPatch, p, h) }
func (r *Router) DELETE(p string, h Handler) { r.Handle(http.MethodDelete, p, h) }

// Mount attaches a plain http.Handler, for the WebSocket upgrade and static
// file serving which do not fit the JSON handler shape.
func (r *Router) Mount(pattern string, h http.Handler) {
	r.mux.Handle(r.prefix+pattern, h)
}

func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) { r.mux.ServeHTTP(w, req) }
