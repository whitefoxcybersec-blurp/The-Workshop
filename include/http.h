#ifndef ARES_HTTP_H
#define ARES_HTTP_H

#include <stddef.h>

#define HTTP_MAX_REQUEST_SIZE (16 * 1024)
#define HTTP_MAX_METHOD_SIZE 16
#define HTTP_MAX_TARGET_SIZE 2048
#define HTTP_MAX_VERSION_SIZE 16

enum http_parse_result {
	HTTP_PARSE_OK = 0,
	HTTP_PARSE_BAD_REQUEST = -1,
	HTTP_PARSE_TOO_LARGE = -2
};

struct http_request {
	char method[HTTP_MAX_METHOD_SIZE];
	char target[HTTP_MAX_TARGET_SIZE];
	char version[HTTP_MAX_VERSION_SIZE];
};

struct http_response {
	int status;
	char content_type[128];
	unsigned char *body;
	size_t body_length;
};

enum http_parse_result http_parse_request(
	const char *data,
	size_t length,
	struct http_request *request);
void http_response_init(struct http_response *response);
int http_response_set(
	struct http_response *response,
	int status,
	const char *content_type,
	const void *body,
	size_t body_length);
void http_response_destroy(struct http_response *response);
int http_send_response(int client_fd, const struct http_response *response);

#endif