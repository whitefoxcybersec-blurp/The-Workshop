#include "http.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>

static const char *reason_phrase(int status)
{
	switch (status) {
	case 200: return "OK";
	case 400: return "Bad Request";
	case 403: return "Forbidden";
	case 404: return "Not Found";
	case 405: return "Method Not Allowed";
	case 413: return "Content Too Large";
	case 431: return "Request Header Fields Too Large";
	case 500: return "Internal Server Error";
	default: return "Internal Server Error";
	}
}

void http_response_init(struct http_response *response)
{
	response->status = 500;
	response->content_type[0] = '\0';
	response->body = NULL;
	response->body_length = 0;
}

int http_response_set(
	struct http_response *response,
	int status,
	const char *content_type,
	const void *body,
	size_t body_length)
{
	unsigned char *copy = NULL;
	size_t content_type_length;

	content_type_length = strlen(content_type);
	if (content_type_length >= sizeof(response->content_type)) {
		return -1;
	}
	if (body_length > 0) {
		copy = malloc(body_length);
		if (copy == NULL) {
			return -1;
		}
		memcpy(copy, body, body_length);
	}
	free(response->body);
	response->body = copy;
	response->body_length = body_length;
	response->status = status;
	memcpy(response->content_type, content_type, content_type_length + 1);
	return 0;
}

void http_response_destroy(struct http_response *response)
{
	free(response->body);
	response->body = NULL;
	response->body_length = 0;
}

static int send_all(int client_fd, const void *data, size_t length)
{
	const unsigned char *cursor = data;

	while (length > 0) {
		ssize_t sent = send(client_fd, cursor, length, 0);
		if (sent < 0 && errno == EINTR) {
			continue;
		}
		if (sent < 0) {
			return -1;
		}
		if (sent == 0) {
			return -1;
		}
		cursor += (size_t)sent;
		length -= (size_t)sent;
	}
	return 0;
}

int http_send_response(int client_fd, const struct http_response *response)
{
	char header[512];
	int header_length;

	header_length = snprintf(header, sizeof(header),
		"HTTP/1.1 %d %s\r\n"
		"Content-Length: %zu\r\n"
		"Content-Type: %s\r\n"
		"X-Content-Type-Options: nosniff\r\n"
		"Connection: close\r\n"
		"%s"
		"\r\n",
		response->status,
		reason_phrase(response->status),
		response->body_length,
		response->content_type[0] ? response->content_type : "text/plain; charset=utf-8",
		response->status == 405 ? "Allow: GET\r\n" : "");
	if (header_length < 0 || (size_t)header_length >= sizeof(header)) {
		return -1;
	}
	if (send_all(client_fd, header, (size_t)header_length) < 0) {
		return -1;
	}
	return send_all(client_fd, response->body, response->body_length);
}