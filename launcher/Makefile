BUILD_DIR := build
BINARY_NAME := bluepacs_viewer

.PHONY: all clean windows linux darwin

all: windows darwin linux

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

windows: $(BUILD_DIR)
	GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o $(BUILD_DIR)/windows_view.exe .

darwin: $(BUILD_DIR)
	GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o $(BUILD_DIR)/macos_view_amd64 .
	GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o $(BUILD_DIR)/macos_view_arm64 .
	lipo -create -output $(BUILD_DIR)/macos_view $(BUILD_DIR)/macos_view_amd64 $(BUILD_DIR)/macos_view_arm64 2>/dev/null || cp $(BUILD_DIR)/macos_view_arm64 $(BUILD_DIR)/macos_view
	rm -f $(BUILD_DIR)/macos_view_amd64 $(BUILD_DIR)/macos_view_arm64

linux: $(BUILD_DIR)
	GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o $(BUILD_DIR)/linux_view .

clean:
	rm -rf $(BUILD_DIR)
