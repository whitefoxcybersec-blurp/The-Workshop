CC ?= cc
CPPFLAGS ?= -D_POSIX_C_SOURCE=200809L -Iinclude
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -Werror -O2
LDFLAGS ?=

BUILD_DIR := build
SERVER_SOURCES := src/main.c src/server.c src/http_parser.c src/response.c src/router.c
SERVER_OBJECTS := $(SERVER_SOURCES:src/%.c=$(BUILD_DIR)/%.o)

.PHONY: all clean test run

all: $(BUILD_DIR)/ares

$(BUILD_DIR)/ares: $(SERVER_OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

$(BUILD_DIR)/%.o: src/%.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c -o $@ $<

$(BUILD_DIR):
	mkdir -p $@

$(BUILD_DIR)/test_parser: tests/test_parser.c src/http_parser.c | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -o $@ $^

test: $(BUILD_DIR)/test_parser
	./$(BUILD_DIR)/test_parser

run: all
	./$(BUILD_DIR)/ares

clean:
	rm -rf $(BUILD_DIR)