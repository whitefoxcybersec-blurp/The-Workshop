#include "router.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

#define HTTP_MAX_FILE_SIZE (16 * 1024 * 1024)

static int hex_value(char character)
{
	if (character >= '0' && character <= '9') return character - '0';
	if (character >= 'a' && character <= 'f') return character - 'a' + 10;
	if (character >= 'A' && character <= 'F') return character - 'A' + 10;
	return -1;
}

static int decode_path(const char *target, char *path, size_t path_size)
{
	const char *cursor = target;
	size_t output_length = 0;

	if (*cursor != '/') {
		return -1;
	}
	while (*cursor != '\0' && *cursor != '?') {
		unsigned char character = (unsigned char)*cursor++;
		if (character == '%') {
			int high;
			int low;
			if (cursor[0] == '\0' || cursor[1] == '\0' ||
				(high = hex_value(cursor[0])) < 0 ||
				(low = hex_value(cursor[1])) < 0) {
				return -1;
			}
			character = (unsigned char)((high << 4) | low);
			cursor += 2;
		}
		if (character == '\0' || character == '\\' || character < 0x20 ||
			character == 0x7f || output_length + 1 >= path_size) {
			return -1;
		}
		path[output_length++] = (char)character;
	}
	path[output_length] = '\0';
	return 0;
}

static int open_public_file(int public_dir_fd, char *relative_path)
{
	char *save_pointer = NULL;
	char *segment;
	int current_fd = dup(public_dir_fd);

	if (current_fd < 0) {
		return -1;
	}
	segment = strtok_r(relative_path, "/", &save_pointer);
	if (segment == NULL) {
		close(current_fd);
		return -1;
	}
	while (segment != NULL) {
		char *next_segment = strtok_r(NULL, "/", &save_pointer);
		int flags = O_RDONLY | O_CLOEXEC | O_NOFOLLOW;
		int next_fd;

		if (strcmp(segment, ".") == 0 || strcmp(segment, "..") == 0) {
			close(current_fd);
			errno = EACCES;
			return -1;
		}
		if (next_segment != NULL) {
			flags |= O_DIRECTORY;
		}
		next_fd = openat(current_fd, segment, flags);
		close(current_fd);
		if (next_fd < 0) {
			return -1;
		}
		current_fd = next_fd;
		segment = next_segment;
	}
	return current_fd;
}

static const char *mime_type(const char *path)
{
	const char *extension = strrchr(path, '.');

	if (extension == NULL) return "application/octet-stream";
	if (strcasecmp(extension, ".html") == 0 || strcasecmp(extension, ".htm") == 0)
		return "text/html; charset=utf-8";
	if (strcasecmp(extension, ".css") == 0) return "text/css; charset=utf-8";
	if (strcasecmp(extension, ".js") == 0) return "text/javascript; charset=utf-8";
	if (strcasecmp(extension, ".json") == 0) return "application/json; charset=utf-8";
	if (strcasecmp(extension, ".txt") == 0) return "text/plain; charset=utf-8";
	if (strcasecmp(extension, ".svg") == 0) return "image/svg+xml";
	if (strcasecmp(extension, ".png") == 0) return "image/png";
	if (strcasecmp(extension, ".jpg") == 0 || strcasecmp(extension, ".jpeg") == 0)
		return "image/jpeg";
	if (strcasecmp(extension, ".gif") == 0) return "image/gif";
	if (strcasecmp(extension, ".ico") == 0) return "image/x-icon";
	return "application/octet-stream";
}

static void set_text_response(
	struct http_response *response,
	int status,
	const char *message)
{
	(void)http_response_set(response, status, "text/plain; charset=utf-8",
		message, strlen(message));
}

static void serve_file(
	int public_dir_fd,
	char *path,
	struct http_response *response)
{
	struct stat file_stat;
	unsigned char *body;
	const char *type = mime_type(path);
	size_t total = 0;
	int file_fd = open_public_file(public_dir_fd, path);

	if (file_fd < 0) {
		set_text_response(response, errno == EACCES || errno == ELOOP ? 403 : 404,
			errno == EACCES || errno == ELOOP ? "Forbidden\n" : "Not Found\n");
		return;
	}
	if (fstat(file_fd, &file_stat) < 0 || !S_ISREG(file_stat.st_mode)) {
		close(file_fd);
		set_text_response(response, 404, "Not Found\n");
		return;
	}
	if (file_stat.st_size < 0 || file_stat.st_size > HTTP_MAX_FILE_SIZE) {
		close(file_fd);
		set_text_response(response, 413, "Content Too Large\n");
		return;
	}
	body = malloc(file_stat.st_size > 0 ? (size_t)file_stat.st_size : 1);
	if (body == NULL) {
		close(file_fd);
		set_text_response(response, 500, "Internal Server Error\n");
		return;
	}
	while (total < (size_t)file_stat.st_size) {
		ssize_t count = read(file_fd, body + total, (size_t)file_stat.st_size - total);
		if (count < 0 && errno == EINTR) {
			continue;
		}
		if (count <= 0) {
			free(body);
			close(file_fd);
			set_text_response(response, 500, "Internal Server Error\n");
			return;
		}
		total += (size_t)count;
	}
	close(file_fd);
	if (http_response_set(response, 200, type, body, total) < 0) {
		free(body);
		set_text_response(response, 500, "Internal Server Error\n");
		return;
	}
	free(body);
}

void router_handle_request(
	int public_dir_fd,
	const struct http_request *request,
	struct http_response *response)
{
	char path[HTTP_MAX_TARGET_SIZE];
	char *relative_path;

	if (strcmp(request->method, "GET") != 0) {
		set_text_response(response, 405, "Method Not Allowed\n");
		return;
	}
	if (decode_path(request->target, path, sizeof(path)) < 0) {
		set_text_response(response, 400, "Bad Request\n");
		return;
	}
	relative_path = path + 1;
	if (*relative_path == '\0') {
		relative_path = "index.html";
	}
	serve_file(public_dir_fd, relative_path, response);
}