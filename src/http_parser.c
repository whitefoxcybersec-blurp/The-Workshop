#include "http.h"

#include <ctype.h>
#include <strings.h>
#include <string.h>

static const char *find_crlf(const char *start, const char *end)
{
	const char *cursor;

	for (cursor = start; cursor + 1 < end; cursor++) {
		if (cursor[0] == '\r' && cursor[1] == '\n') {
			return cursor;
		}
	}
	return NULL;
}

static int is_token_character(unsigned char character)
{
	if (character == '\0') {
		return 0;
	}
	if (isalnum(character)) {
		return 1;
	}
	return strchr("!#$%&'*+-.^_`|~", character) != NULL;
}

static int is_valid_token(const char *start, size_t length)
{
	size_t index;

	if (length == 0) {
		return 0;
	}
	for (index = 0; index < length; index++) {
		if (!is_token_character((unsigned char)start[index])) {
			return 0;
		}
	}
	return 1;
}

enum http_parse_result http_parse_request(
	const char *data,
	size_t length,
	struct http_request *request)
{
	const char *end;
	const char *headers_end;
	const char *line_end;
	const char *first_space;
	const char *second_space;
	const char *cursor;
	int host_seen = 0;
	size_t method_length;
	size_t target_length;
	size_t version_length;

	if (data == NULL || request == NULL) {
		return HTTP_PARSE_BAD_REQUEST;
	}
	if (length > HTTP_MAX_REQUEST_SIZE) {
		return HTTP_PARSE_TOO_LARGE;
	}
	end = data + length;
	if (length < 4) {
		return HTTP_PARSE_BAD_REQUEST;
	}
	headers_end = NULL;
	for (cursor = data; cursor + 3 < end; cursor++) {
		if (memcmp(cursor, "\r\n\r\n", 4) == 0) {
			headers_end = cursor;
			break;
		}
	}
	if (headers_end == NULL) {
		return HTTP_PARSE_BAD_REQUEST;
	}

	line_end = find_crlf(data, headers_end + 2);
	if (line_end == NULL) {
		return HTTP_PARSE_BAD_REQUEST;
	}
	first_space = memchr(data, ' ', (size_t)(line_end - data));
	if (first_space == NULL) {
		return HTTP_PARSE_BAD_REQUEST;
	}
	second_space = memchr(first_space + 1, ' ', (size_t)(line_end - first_space - 1));
	if (second_space == NULL || memchr(second_space + 1, ' ',
		(size_t)(line_end - second_space - 1)) != NULL) {
		return HTTP_PARSE_BAD_REQUEST;
	}

	method_length = (size_t)(first_space - data);
	target_length = (size_t)(second_space - first_space - 1);
	version_length = (size_t)(line_end - second_space - 1);
	if (!is_valid_token(data, method_length) || target_length == 0 ||
		version_length == 0 || method_length >= sizeof(request->method) ||
		target_length >= sizeof(request->target) ||
		version_length >= sizeof(request->version)) {
		return HTTP_PARSE_BAD_REQUEST;
	}
	for (cursor = first_space + 1; cursor < second_space; cursor++) {
		unsigned char character = (unsigned char)*cursor;
		if (character <= 0x20 || character == 0x7f) {
			return HTTP_PARSE_BAD_REQUEST;
		}
	}
	memcpy(request->method, data, method_length);
	request->method[method_length] = '\0';
	memcpy(request->target, first_space + 1, target_length);
	request->target[target_length] = '\0';
	memcpy(request->version, second_space + 1, version_length);
	request->version[version_length] = '\0';
	if (strcmp(request->version, "HTTP/1.1") != 0 &&
		strcmp(request->version, "HTTP/1.0") != 0) {
		return HTTP_PARSE_BAD_REQUEST;
	}

	cursor = line_end + 2;
	while (cursor < headers_end) {
		const char *header_end = find_crlf(cursor, headers_end + 2);
		const char *colon;
		const char *value_start;
		const char *value_end;
		const char *value_cursor;
		size_t name_length;

		if (header_end == NULL || header_end == cursor ||
			*cursor == ' ' || *cursor == '\t') {
			return HTTP_PARSE_BAD_REQUEST;
		}
		colon = memchr(cursor, ':', (size_t)(header_end - cursor));
		if (colon == NULL) {
			return HTTP_PARSE_BAD_REQUEST;
		}
		name_length = (size_t)(colon - cursor);
		if (!is_valid_token(cursor, name_length)) {
			return HTTP_PARSE_BAD_REQUEST;
		}
		value_start = colon + 1;
		while (value_start < header_end && (*value_start == ' ' || *value_start == '\t')) {
			value_start++;
		}
		value_end = header_end;
		while (value_end > value_start &&
			(value_end[-1] == ' ' || value_end[-1] == '\t')) {
			value_end--;
		}
		for (value_cursor = value_start; value_cursor < value_end; value_cursor++) {
			unsigned char character = (unsigned char)*value_cursor;
			if ((character < 0x20 && character != '\t') || character == 0x7f) {
				return HTTP_PARSE_BAD_REQUEST;
			}
		}
		if (name_length == 4 && strncasecmp(cursor, "Host", 4) == 0) {
			if (host_seen || value_start == value_end) {
				return HTTP_PARSE_BAD_REQUEST;
			}
			host_seen = 1;
		}
		cursor = header_end + 2;
	}
	if (strcmp(request->version, "HTTP/1.1") == 0 && !host_seen) {
		return HTTP_PARSE_BAD_REQUEST;
	}
	return HTTP_PARSE_OK;
}