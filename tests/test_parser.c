#include "http.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static void test_valid_http11_request(void)
{
	const char request_text[] =
		"GET /health?full=1 HTTP/1.1\r\n"
		"Host: localhost:8080\r\n"
		"User-Agent: test\r\n"
		"\r\n";
	struct http_request request;

	assert(http_parse_request(request_text, sizeof(request_text) - 1, &request) == HTTP_PARSE_OK);
	assert(strcmp(request.method, "GET") == 0);
	assert(strcmp(request.target, "/health?full=1") == 0);
	assert(strcmp(request.version, "HTTP/1.1") == 0);
}

static void test_http10_without_host(void)
{
	const char request_text[] = "GET / HTTP/1.0\r\n\r\n";
	struct http_request request;

	assert(http_parse_request(request_text, sizeof(request_text) - 1, &request) == HTTP_PARSE_OK);
}

static void test_http11_requires_host(void)
{
	const char request_text[] = "GET / HTTP/1.1\r\n\r\n";
	struct http_request request;

	assert(http_parse_request(request_text, sizeof(request_text) - 1, &request) ==
		HTTP_PARSE_BAD_REQUEST);
}

static void test_rejects_malformed_header(void)
{
	const char request_text[] = "GET / HTTP/1.1\r\nHost localhost\r\n\r\n";
	struct http_request request;

	assert(http_parse_request(request_text, sizeof(request_text) - 1, &request) ==
		HTTP_PARSE_BAD_REQUEST);
}

static void test_rejects_unknown_version(void)
{
	const char request_text[] = "GET / HTTP/2.0\r\nHost: localhost\r\n\r\n";
	struct http_request request;

	assert(http_parse_request(request_text, sizeof(request_text) - 1, &request) ==
		HTTP_PARSE_BAD_REQUEST);
}

static void test_rejects_control_byte_in_target(void)
{
	const char request_text[] = "GET /a\0b HTTP/1.1\r\nHost: localhost\r\n\r\n";
	struct http_request request;

	assert(http_parse_request(request_text, sizeof(request_text) - 1, &request) ==
		HTTP_PARSE_BAD_REQUEST);
}

static void test_enforces_size_limit(void)
{
	struct http_request request;

	assert(http_parse_request("", HTTP_MAX_REQUEST_SIZE + 1, &request) == HTTP_PARSE_TOO_LARGE);
}

int main(void)
{
	test_valid_http11_request();
	test_http10_without_host();
	test_http11_requires_host();
	test_rejects_malformed_header();
	test_rejects_unknown_version();
	test_rejects_control_byte_in_target();
	test_enforces_size_limit();
	puts("parser tests passed");
	return 0;
}