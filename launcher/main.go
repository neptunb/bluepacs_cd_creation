package main

import (
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
)

func main() {
	execPath, err := os.Executable()
	if err != nil {
		log.Fatal("Cannot determine executable path:", err)
	}
	baseDir := filepath.Dir(execPath)

	studyDir := filepath.Join(baseDir, "STUDY")
	viewerDir := filepath.Join(baseDir, "viewer")

	if _, err := os.Stat(studyDir); os.IsNotExist(err) {
		log.Fatal("STUDY directory not found at:", studyDir)
	}
	if _, err := os.Stat(viewerDir); os.IsNotExist(err) {
		log.Fatal("viewer directory not found at:", viewerDir)
	}

	port, err := findFreePort()
	if err != nil {
		log.Fatal("Cannot find free port:", err)
	}

	addr := fmt.Sprintf("127.0.0.1:%d", port)
	url := fmt.Sprintf("http://%s", addr)

	fmt.Println("==============================================")
	fmt.Println("  BluePACS DICOM Viewer")
	fmt.Println("==============================================")
	fmt.Printf("  Starting viewer at: %s\n", url)
	fmt.Println("  Press Ctrl+C to stop")
	fmt.Println("==============================================")

	server := NewServer(addr, viewerDir, studyDir)

	go func() {
		if err := openBrowser(url); err != nil {
			fmt.Printf("  Please open your browser to: %s\n", url)
		}
	}()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigChan
		fmt.Println("\nShutting down...")
		os.Exit(0)
	}()

	log.Fatal(server.Start())
}

func findFreePort() (int, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer listener.Close()
	return listener.Addr().(*net.TCPAddr).Port, nil
}
