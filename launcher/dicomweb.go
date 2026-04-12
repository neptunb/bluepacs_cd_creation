package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"

	"github.com/suyashkumar/dicom"
	"github.com/suyashkumar/dicom/pkg/tag"
)

type DicomFile struct {
	Path                      string
	StudyInstanceUID          string
	SeriesInstanceUID         string
	SOPInstanceUID            string
	SOPClassUID               string
	Modality                  string
	SeriesNumber              string
	SeriesDescription         string
	InstanceNumber            string
	StudyDate                 string
	StudyDescription          string
	PatientName               string
	PatientID                 string
	TransferSyntaxUID         string
	Rows                      int
	Columns                   int
	SamplesPerPixel           int
	BitsAllocated             int
	BitsStored                int
	HighBit                   int
	PixelRepresentation       int
	PhotometricInterpretation string
	NumberOfFrames            string
	ImageOrientationPatient   []string
	ImagePositionPatient      []string
	PixelSpacing              []string
	WindowCenter              []string
	WindowWidth               []string
}

func setDicomWebJSONHeaders(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "application/dicom+json")
	w.Header().Set("Cross-Origin-Resource-Policy", "cross-origin")
}

func firstIntIn(ds dicom.Dataset, t tag.Tag) int {
	el, err := ds.FindElementByTag(t)
	if err != nil {
		return 0
	}
	v := el.Value.GetValue()
	switch x := v.(type) {
	case []int:
		if len(x) > 0 {
			return x[0]
		}
	case []uint16:
		if len(x) > 0 {
			return int(x[0])
		}
	case []uint32:
		if len(x) > 0 {
			return int(x[0])
		}
	}
	return 0
}

func stringSliceFrom(ds dicom.Dataset, t tag.Tag) []string {
	el, err := ds.FindElementByTag(t)
	if err != nil {
		return nil
	}
	v := el.Value.GetValue()
	switch x := v.(type) {
	case []string:
		return append([]string(nil), x...)
	case string:
		if strings.TrimSpace(x) == "" {
			return nil
		}
		return []string{x}
	case []float64:
		out := make([]string, len(x))
		for i, f := range x {
			out[i] = strconv.FormatFloat(f, 'g', -1, 64)
		}
		return out
	case []int:
		out := make([]string, len(x))
		for i, n := range x {
			out[i] = strconv.Itoa(n)
		}
		return out
	}
	return nil
}

type DicomWebHandler struct {
	dicomDir string
	files    []DicomFile
	once     sync.Once
}

func NewDicomWebHandler(dicomDir string) *DicomWebHandler {
	return &DicomWebHandler{dicomDir: dicomDir}
}

func instanceNumberSortKey(n string) int {
	n = strings.TrimSpace(n)
	if n == "" {
		return 1 << 30
	}
	v, err := strconv.Atoi(n)
	if err != nil {
		return 1 << 29
	}
	return v
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

	df.TransferSyntaxUID = getStringTag(tag.TransferSyntaxUID)
	df.Rows = firstIntIn(dataset, tag.Rows)
	df.Columns = firstIntIn(dataset, tag.Columns)
	df.SamplesPerPixel = firstIntIn(dataset, tag.SamplesPerPixel)
	df.BitsAllocated = firstIntIn(dataset, tag.BitsAllocated)
	df.BitsStored = firstIntIn(dataset, tag.BitsStored)
	df.HighBit = firstIntIn(dataset, tag.HighBit)
	df.PixelRepresentation = firstIntIn(dataset, tag.PixelRepresentation)
	df.PhotometricInterpretation = getStringTag(tag.PhotometricInterpretation)
	df.NumberOfFrames = getStringTag(tag.NumberOfFrames)
	df.ImageOrientationPatient = stringSliceFrom(dataset, tag.ImageOrientationPatient)
	df.ImagePositionPatient = stringSliceFrom(dataset, tag.ImagePositionPatient)
	df.PixelSpacing = stringSliceFrom(dataset, tag.PixelSpacing)
	df.WindowCenter = stringSliceFrom(dataset, tag.WindowCenter)
	df.WindowWidth = stringSliceFrom(dataset, tag.WindowWidth)
	if df.Rows > 0 && df.Columns > 0 && df.SamplesPerPixel == 0 {
		df.SamplesPerPixel = 1
	}

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

	setDicomWebJSONHeaders(w)
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

	setDicomWebJSONHeaders(w)
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

	var matching []DicomFile
	for _, f := range h.files {
		if f.StudyInstanceUID != studyUID || f.SeriesInstanceUID != seriesUID {
			continue
		}
		matching = append(matching, f)
	}
	sort.Slice(matching, func(i, j int) bool {
		ki, kj := instanceNumberSortKey(matching[i].InstanceNumber), instanceNumberSortKey(matching[j].InstanceNumber)
		if ki != kj {
			return ki < kj
		}
		return matching[i].SOPInstanceUID < matching[j].SOPInstanceUID
	})

	results := make([]map[string]interface{}, 0, len(matching))
	for _, f := range matching {
		instance := map[string]interface{}{
			"00080018": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPInstanceUID}},
			"00080016": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPClassUID}},
			"0020000D": map[string]interface{}{"vr": "UI", "Value": []string{f.StudyInstanceUID}},
			"0020000E": map[string]interface{}{"vr": "UI", "Value": []string{f.SeriesInstanceUID}},
			"00200013": map[string]interface{}{"vr": "IS", "Value": []string{f.InstanceNumber}},
		}
		results = append(results, instance)
	}

	setDicomWebJSONHeaders(w)
	json.NewEncoder(w).Encode(results)
}

func (h *DicomWebHandler) sopUIDFromPath(r *http.Request) string {
	parts := strings.Split(strings.Trim(r.URL.Path, "/"), "/")
	for i, p := range parts {
		if p == "instances" && i+1 < len(parts) {
			return parts[i+1]
		}
	}
	return ""
}

func (h *DicomWebHandler) writeInstanceDICOM(w http.ResponseWriter, r *http.Request, sopUID string) {
	for _, f := range h.files {
		if f.SOPInstanceUID == sopUID {
			data, err := os.ReadFile(f.Path)
			if err != nil {
				http.Error(w, "Failed to read file", http.StatusInternalServerError)
				return
			}
			w.Header().Set("Content-Type", "application/dicom")
			w.Header().Set("Cross-Origin-Resource-Policy", "cross-origin")
			w.Write(data)
			return
		}
	}
	http.NotFound(w, r)
}

// HandleRetrieveInstance serves WADO-RS GET .../instances/{sop} (full DICOM file).
func (h *DicomWebHandler) HandleRetrieveInstance(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()
	h.writeInstanceDICOM(w, r, h.sopUIDFromPath(r))
}

func (h *DicomWebHandler) HandleFrames(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()
	sopUID := h.sopUIDFromPath(r)
	if sopUID == "" {
		http.NotFound(w, r)
		return
	}
	// Single-frame object: return full instance; multi-frame still served as one DICOM.
	h.writeInstanceDICOM(w, r, sopUID)
}

func (h *DicomWebHandler) instanceMetaMap(f DicomFile) map[string]interface{} {
	m := map[string]interface{}{
		"00080018": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPInstanceUID}},
		"00080016": map[string]interface{}{"vr": "UI", "Value": []string{f.SOPClassUID}},
		"0020000D": map[string]interface{}{"vr": "UI", "Value": []string{f.StudyInstanceUID}},
		"0020000E": map[string]interface{}{"vr": "UI", "Value": []string{f.SeriesInstanceUID}},
		"00080060": map[string]interface{}{"vr": "CS", "Value": []string{f.Modality}},
		"00200013": map[string]interface{}{"vr": "IS", "Value": []string{f.InstanceNumber}},
	}
	if f.TransferSyntaxUID != "" {
		m["00020010"] = map[string]interface{}{"vr": "UI", "Value": []string{f.TransferSyntaxUID}}
	}
	if f.Rows > 0 {
		m["00280010"] = map[string]interface{}{"vr": "US", "Value": []int{f.Rows}}
	}
	if f.Columns > 0 {
		m["00280011"] = map[string]interface{}{"vr": "US", "Value": []int{f.Columns}}
	}
	if f.SamplesPerPixel > 0 {
		m["00280002"] = map[string]interface{}{"vr": "US", "Value": []int{f.SamplesPerPixel}}
	}
	if f.BitsAllocated > 0 {
		m["00280100"] = map[string]interface{}{"vr": "US", "Value": []int{f.BitsAllocated}}
	}
	if f.BitsStored > 0 {
		m["00280101"] = map[string]interface{}{"vr": "US", "Value": []int{f.BitsStored}}
	}
	if f.BitsStored > 0 {
		hb := f.HighBit
		if hb == 0 {
			hb = f.BitsStored - 1
		}
		m["00280102"] = map[string]interface{}{"vr": "US", "Value": []int{hb}}
	}
	if f.BitsAllocated > 0 {
		m["00280103"] = map[string]interface{}{"vr": "US", "Value": []int{f.PixelRepresentation}}
	}
	if f.PhotometricInterpretation != "" {
		m["00280004"] = map[string]interface{}{"vr": "CS", "Value": []string{f.PhotometricInterpretation}}
	}
	if strings.TrimSpace(f.NumberOfFrames) != "" {
		m["00280008"] = map[string]interface{}{"vr": "IS", "Value": []string{f.NumberOfFrames}}
	}
	if len(f.ImageOrientationPatient) > 0 {
		m["00200037"] = map[string]interface{}{"vr": "DS", "Value": f.ImageOrientationPatient}
	}
	if len(f.ImagePositionPatient) > 0 {
		m["00200032"] = map[string]interface{}{"vr": "DS", "Value": f.ImagePositionPatient}
	}
	if len(f.PixelSpacing) > 0 {
		m["00280030"] = map[string]interface{}{"vr": "DS", "Value": f.PixelSpacing}
	}
	if len(f.WindowCenter) > 0 {
		m["00281050"] = map[string]interface{}{"vr": "DS", "Value": f.WindowCenter}
	}
	if len(f.WindowWidth) > 0 {
		m["00281051"] = map[string]interface{}{"vr": "DS", "Value": f.WindowWidth}
	}
	return m
}

// HandleInstanceMetadata serves WADO-RS .../instances/{sop}/metadata (one instance).
func (h *DicomWebHandler) HandleInstanceMetadata(w http.ResponseWriter, r *http.Request) {
	h.loadFiles()
	sop := h.sopUIDFromPath(r)
	if sop == "" {
		http.NotFound(w, r)
		return
	}
	for _, f := range h.files {
		if f.SOPInstanceUID == sop {
			setDicomWebJSONHeaders(w)
			json.NewEncoder(w).Encode([]map[string]interface{}{h.instanceMetaMap(f)})
			return
		}
	}
	http.NotFound(w, r)
}

// HandleMetadata serves series-level .../series/{series}/metadata (bulk) or study-level metadata.
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
		results = append(results, h.instanceMetaMap(f))
	}

	setDicomWebJSONHeaders(w)
	json.NewEncoder(w).Encode(results)
}
