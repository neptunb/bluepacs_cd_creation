package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
)

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

func (s *Server) Start() error {
	mux := http.NewServeMux()

	mux.HandleFunc("/dicomweb/", s.handleDicomWeb)
	mux.HandleFunc("/api/config", s.handleConfig)
	mux.Handle("/", http.FileServer(http.Dir(s.viewerDir)))

	handler := corsMiddleware(mux)

	log.Printf("Server listening on %s", s.addr)
	return http.ListenAndServe(s.addr, handler)
}

func (s *Server) handleConfig(w http.ResponseWriter, r *http.Request) {
	config := map[string]interface{}{
		"routerBasename": "/",
		"dataSources": []map[string]interface{}{
			{
				"namespace":  "@ohif/extension-default.dataSourcesModule.dicomweb",
				"sourceName": "local",
				"configuration": map[string]interface{}{
					"friendlyName": "Local DICOM Files",
					"name":         "local",
					"wadoUriRoot":  fmt.Sprintf("http://%s/dicomweb", s.addr),
					"qidoRoot":     fmt.Sprintf("http://%s/dicomweb", s.addr),
					"wadoRoot":     fmt.Sprintf("http://%s/dicomweb", s.addr),
					"qidoSupportsIncludeField": false,
					"imageRendering":           "wadors",
					"thumbnailRendering":       "wadors",
					"enableStudyLazyLoad":      true,
					"supportsFuzzyMatching":    false,
					"supportsWildcard":         false,
				},
			},
		},
		"defaultDataSourceName": "local",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(config)
}

func (s *Server) handleDicomWeb(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/dicomweb")

	switch {
	case path == "/studies" || path == "/studies/":
		s.dicomWeb.HandleStudies(w, r)
	case strings.Contains(path, "/series") && !strings.Contains(path, "/instances"):
		s.dicomWeb.HandleSeries(w, r)
	case strings.Contains(path, "/instances"):
		s.dicomWeb.HandleInstances(w, r)
	case strings.Contains(path, "/frames/"):
		s.dicomWeb.HandleFrames(w, r)
	case strings.HasSuffix(path, "/metadata"):
		s.dicomWeb.HandleMetadata(w, r)
	default:
		http.NotFound(w, r)
	}
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
