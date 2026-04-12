package main

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"text/template"
)

//go:embed ohif_app_config.js.tpl
var ohifAppConfigTpl string

var ohifAppConfigTemplate = template.Must(template.New("ohif").Parse(ohifAppConfigTpl))

type Server struct {
	addr      string
	viewerDir string
	dicomWeb  *DicomWebHandler
}

func NewServer(addr, viewerDir, dicomDir string) *Server {
	return &Server{
		addr:      addr,
		viewerDir: viewerDir,
		dicomWeb:  NewDicomWebHandler(dicomDir),
	}
}

// CORP lets scripts, WASM, and workers load under COEP: require-corp (same-origin + strict checks in some engines).
func corpStaticFileServer(root string) http.Handler {
	fs := http.FileServer(http.Dir(root))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cross-Origin-Resource-Policy", "cross-origin")
		fs.ServeHTTP(w, r)
	})
}

func dicomWebRootFromRequest(r *http.Request) string {
	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	return fmt.Sprintf("%s://%s/dicomweb", scheme, r.Host)
}

func (s *Server) Start() error {
	mux := http.NewServeMux()

	// OHIF is normally built with PUBLIC_URL=/ (default). If you use PUBLIC_URL=/viewer/, also request this path.
	mux.HandleFunc("/app-config.js", s.handleAppConfigJS)
	mux.HandleFunc("/viewer/app-config.js", s.handleAppConfigJS)
	mux.HandleFunc("/dicomweb/", s.handleDicomWeb)
	mux.HandleFunc("/api/config", s.handleConfig)
	mux.Handle("/", corpStaticFileServer(s.viewerDir))

	// OHIF v3 / Cornerstone3D expect cross-origin isolation for SharedArrayBuffer + WASM.
	// Without these, Safari and some Chrome builds show a blank/black UI after load.
	handler := crossOriginIsolationMiddleware(corsMiddleware(mux))

	log.Printf("Server listening on %s", s.addr)
	return http.ListenAndServe(s.addr, handler)
}

func crossOriginIsolationMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cross-Origin-Opener-Policy", "same-origin")
		w.Header().Set("Cross-Origin-Embedder-Policy", "require-corp")
		next.ServeHTTP(w, r)
	})
}

func (s *Server) handleAppConfigJS(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	root := dicomWebRootFromRequest(r)
	quoted, err := json.Marshal(root)
	if err != nil {
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/javascript; charset=utf-8")
	w.Header().Set("Cross-Origin-Resource-Policy", "cross-origin")
	// Use text/template (not html/template): html/template escapes " to &#34; and breaks JS.
	data := struct {
		DicomWebRoot string
	}{DicomWebRoot: string(quoted)}
	if err := ohifAppConfigTemplate.Execute(w, data); err != nil {
		log.Printf("app-config template: %v", err)
	}
}

func (s *Server) handleConfig(w http.ResponseWriter, r *http.Request) {
	root := dicomWebRootFromRequest(r)
	config := map[string]interface{}{
		"routerBasename": nil,
		"dataSources": []map[string]interface{}{
			{
				"namespace":  "@ohif/extension-default.dataSourcesModule.dicomweb",
				"sourceName": "bluepacs-local",
				"configuration": map[string]interface{}{
					"friendlyName": "Images on this disc",
					"name":         "bluepacs-local",
					"wadoUriRoot":  root,
					"qidoRoot":     root,
					"wadoRoot":     root,
					"qidoSupportsIncludeField": false,
					"imageRendering":           "wadors",
					"thumbnailRendering":       "wadors",
					"staticWado":               true,
					"singlepart":               "image,bulkdata,video",
					"enableStudyLazyLoad":      true,
					"supportsFuzzyMatching":    false,
					"supportsWildcard":         false,
					"omitQuotationForMultipartRequest": true,
					"bulkDataURI": map[string]interface{}{
						"enabled": false,
					},
				},
			},
		},
		"defaultDataSourceName": "bluepacs-local",
	}

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cross-Origin-Resource-Policy", "cross-origin")
	json.NewEncoder(w).Encode(config)
}

func (s *Server) handleDicomWeb(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/dicomweb")
	// Bare /dicomweb or /dicomweb/ is not QIDO — browsers show 404. Send users to studies.
	if path == "" || path == "/" {
		if r.Method == http.MethodGet || r.Method == http.MethodHead {
			http.Redirect(w, r, "/dicomweb/studies", http.StatusTemporaryRedirect)
			return
		}
	}

	// Order matters: WADO paths contain "/instances" too. OHIF calls e.g.
	// .../instances/{sop}/frames/1 and .../instances/{sop}/metadata — not the QIDO list.
	switch {
	case path == "/studies" || path == "/studies/":
		s.dicomWeb.HandleStudies(w, r)
	case strings.Contains(path, "/instances/") && strings.Contains(path, "/frames/"):
		s.dicomWeb.HandleFrames(w, r)
	case strings.Contains(path, "/instances/") && strings.HasSuffix(path, "/metadata"):
		s.dicomWeb.HandleInstanceMetadata(w, r)
	case strings.HasSuffix(path, "/metadata"):
		s.dicomWeb.HandleMetadata(w, r)
	case isQidoInstanceList(path):
		s.dicomWeb.HandleInstances(w, r)
	case strings.Contains(path, "/instances/") && isWadoRetrieveInstance(path):
		s.dicomWeb.HandleRetrieveInstance(w, r)
	case strings.Contains(path, "/rendered"):
		http.Error(w, "rendered resources are not supported on this disc", http.StatusNotImplemented)
	case strings.Contains(path, "/series"):
		s.dicomWeb.HandleSeries(w, r)
	default:
		log.Printf("dicomweb 404: %s %s", r.Method, r.URL.Path)
		http.NotFound(w, r)
	}
}

// QIDO-RS instance search: .../series/{seriesUID}/instances with nothing after "instances".
func isQidoInstanceList(path string) bool {
	if !strings.Contains(path, "/instances") {
		return false
	}
	if strings.Contains(path, "/instances/") {
		return false
	}
	return strings.HasSuffix(path, "/instances") || strings.HasSuffix(path, "/instances/")
}

// WADO-RS retrieve instance: .../instances/{SOPInstanceUID} (no /metadata, /frames, /rendered).
func isWadoRetrieveInstance(path string) bool {
	if !strings.Contains(path, "/instances/") {
		return false
	}
	i := strings.Index(path, "/instances/")
	tail := path[i+len("/instances/"):]
	tail = strings.TrimSuffix(tail, "/")
	if tail == "" {
		return false
	}
	segs := strings.Split(tail, "/")
	if len(segs) != 1 {
		return false
	}
	return segs[0] != ""
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Accept")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
