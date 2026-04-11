package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/suyashkumar/dicom"
	"github.com/suyashkumar/dicom/pkg/tag"
)

type DicomFile struct {
	Path              string
	StudyInstanceUID  string
	SeriesInstanceUID string
	SOPInstanceUID    string
	SOPClassUID       string
	Modality          string
	SeriesNumber      string
	SeriesDescription string
	InstanceNumber    string
	StudyDate         string
	StudyDescription  string
	PatientName       string
	PatientID         string
	Rows              int
	Columns           int
}

type DicomWebHandler struct {
	dicomDir string
	files    []DicomFile
	once     sync.Once
}

func NewDicomWebHandler(dicomDir string) *DicomWebHandler {
	return &DicomWebHandler{dicomDir: dicomDir}
}

func (h *DicomWebHandler) loadFiles() {
	h.once.Do(func() {
		log.Println("Scanning DICOM files...")
		filepath.Walk(h.dicomDir, func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}

			ext := strings.ToLower(filepath.Ext(path))
			if ext != ".dcm" && ext != "" {
				if ext != ".xml" && ext != ".txt" && ext != ".json" {
					df := h.parseDicomFile(path)
					if df != nil {
						h.files = append(h.files, *df)
					}
				}
				return nil
			}

			df := h.parseDicomFile(path)
			if df != nil {
				h.files = append(h.files, *df)
			}
			return nil
		})
		log.Printf("Found %d DICOM files", len(h.files))
	})
}

func (h *DicomWebHandler) parseDicomFile(path string) *DicomFile {
	dataset, err := dicom.ParseFile(path, nil)
	if err != nil {
		return nil
	}

	df := &DicomFile{Path: path}

	getStringTag := func(t tag.Tag) string {
		el, err := dataset.FindElementByTag(t)
		if err != nil {
			return ""
		}
		vals := el.Value.GetValue()
		if vals == nil {
			return ""
		}
		strs, ok := vals.([]string)
		if ok && len(strs) > 0 {
			return strs[0]
		}
		return fmt.Sprintf("%v", vals)
	}

	df.StudyInstanceUID = getStringTag(tag.StudyInstanceUID)
	df.SeriesInstanceUID = getStringTag(tag.SeriesInstanceUID)
	df.SOPInstanceUID = getStringTag(tag.SOPInstanceUID)
	df.SOPClassUID = getStringTag(tag.SOPClassUID)
	df.Modality = getStringTag(tag.Modality)
	df.SeriesNumber = getStringTag(tag.SeriesNumber)
	df.SeriesDescription = getStringTag(tag.SeriesDescription)
	df.InstanceNumber = getStringTag(tag.InstanceNumber)
	df.StudyDate = getStringTag(tag.StudyDate)
	df.StudyDescription = getStringTag(tag.StudyDescription)
	df.PatientName = getStringTag(tag.PatientName)
	df.PatientID = getStringTag(tag.PatientID)

	if df.StudyInstanceUID == "" || df.SeriesInstanceUID == "" || df.SOPInstanceUID == "" {
		return nil
	}

	return df
}

func (h *DicomWebHandler) HandleStudies(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()

	studyMap := make(map[string]map[string]interface{})
	for _, f := range h.files {
		if _, exists := studyMap[f.StudyInstanceUID]; !exists {
			studyMap[f.StudyInstanceUID] = map[string]interface{}{
				"0020000D": map[string]interface{}{"vr": "UI", "Value": []string{f.StudyInstanceUID}},
				"00080020": map[string]interface{}{"vr": "DA", "Value": []string{f.StudyDate}},
				"00081030": map[string]interface{}{"vr": "LO", "Value": []string{f.StudyDescription}},
				"00100010": map[string]interface{}{"vr": "PN", "Value": []map[string]string{{"Alphabetic": f.PatientName}}},
				"00100020": map[string]interface{}{"vr": "LO", "Value": []string{f.PatientID}},
				"00080061": map[string]interface{}{"vr": "CS", "Value": []string{f.Modality}},
			}
		}
	}

	results := make([]map[string]interface{}, 0, len(studyMap))
	for _, v := range studyMap {
		results = append(results, v)
	}

	w.Header().Set("Content-Type", "application/dicom+json")
	json.NewEncoder(w).Encode(results)
}

func (h *DicomWebHandler) HandleSeries(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()

	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	var studyUID string
	for i, p := range parts {
		if p == "studies" && i+1 < len(parts) {
			studyUID = parts[i+1]
			break
		}
	}

	seriesMap := make(map[string]map[string]interface{})
	for _, f := range h.files {
		if f.StudyInstanceUID != studyUID {
			continue
		}
		if _, exists := seriesMap[f.SeriesInstanceUID]; !exists {
			seriesMap[f.SeriesInstanceUID] = map[string]interface{}{
				"0020000E": map[string]interface{}{"vr": "UI", "Value": []string{f.SeriesInstanceUID}},
				"0020000D": map[string]interface{}{"vr": "UI", "Value": []string{f.StudyInstanceUID}},
				"00200011": map[string]interface{}{"vr": "IS", "Value": []string{f.SeriesNumber}},
				"0008103E": map[string]interface{}{"vr": "LO", "Value": []string{f.SeriesDescription}},
				"00080060": map[string]interface{}{"vr": "CS", "Value": []string{f.Modality}},
			}
		}
	}

	results := make([]map[string]interface{}, 0, len(seriesMap))
	for _, v := range seriesMap {
		results = append(results, v)
	}

	w.Header().Set("Content-Type", "application/dicom+json")
	json.NewEncoder(w).Encode(results)
}

func (h *DicomWebHandler) HandleInstances(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()

	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	var studyUID, seriesUID string
	for i, p := range parts {
		if p == "studies" && i+1 < len(parts) {
			studyUID = parts[i+1]
		}
		if p == "series" && i+1 < len(parts) {
			seriesUID = parts[i+1]
		}
	}

	var results []map[string]interface{}
	for _, f := range h.files {
		if f.StudyInstanceUID != studyUID || f.SeriesInstanceUID != seriesUID {
			continue
		}
		instance := map[string]interface{}{
			"00080018": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPInstanceUID}},
			"00080016": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPClassUID}},
			"0020000D": map[string]interface{}{"vr": "UI", "Value": []string{f.StudyInstanceUID}},
			"0020000E": map[string]interface{}{"vr": "UI", "Value": []string{f.SeriesInstanceUID}},
			"00200013": map[string]interface{}{"vr": "IS", "Value": []string{f.InstanceNumber}},
		}
		results = append(results, instance)
	}

	w.Header().Set("Content-Type", "application/dicom+json")
	json.NewEncoder(w).Encode(results)
}

func (h *DicomWebHandler) HandleFrames(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()

	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	var sopUID string
	for i, p := range parts {
		if p == "instances" && i+1 < len(parts) {
			sopUID = parts[i+1]
			break
		}
	}

	for _, f := range h.files {
		if f.SOPInstanceUID == sopUID {
			data, err := os.ReadFile(f.Path)
			if err != nil {
				http.Error(w, "Failed to read file", http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/dicom")
			w.Header().Set("Transfer-Encoding", "chunked")
			w.Write(data)
			return
		}
	}

	http.NotFound(w, r)
}

func (h *DicomWebHandler) HandleMetadata(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()

	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	var studyUID, seriesUID string
	for i, p := range parts {
		if p == "studies" && i+1 < len(parts) {
			studyUID = parts[i+1]
		}
		if p == "series" && i+1 < len(parts) {
			seriesUID = parts[i+1]
		}
	}

	var results []map[string]interface{}
	for _, f := range h.files {
		if studyUID != "" && f.StudyInstanceUID != studyUID {
			continue
		}
		if seriesUID != "" && f.SeriesInstanceUID != seriesUID {
			continue
		}
		meta := map[string]interface{}{
			"00080018": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPInstanceUID}},
			"00080016": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPClassUID}},
			"0020000D": map[string]interface{}{"vr": "UI", "Value": []string{f.StudyInstanceUID}},
			"0020000E": map[string]interface{}{"vr": "UI", "Value": []string{f.SeriesInstanceUID}},
			"00080060": map[string]interface{}{"vr": "CS", "Value": []string{f.Modality}},
			"00200013": map[string]interface{}{"vr": "IS", "Value": []string{f.InstanceNumber}},
		}
		results = append(results, meta)
	}

	w.Header().Set("Content-Type", "application/dicom+json")
	json.NewEncoder(w).Encode(results)
}
