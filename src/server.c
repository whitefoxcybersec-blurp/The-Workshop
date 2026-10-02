#include "http.h"
#include "router.h"
#include "server.h"

#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#include <fcntl.h>

#define SERVER_PORT 8080
#define SERVER_BACKLOG 64

static volatile sig_atomic_t server_running = 1;

static void stop_server(int signal_number)
{
	(void)signal_number;
	server_running = 0;
}

static const char *find_header_end(const char *data, size_t length)
{
	size_t index;

	if (length < 4) return NULL;
	for (index = 0; index + 3 < length; index++) {
		if (memcmp(data + index, "\r\n\r\n", 4) == 0) {
			return data + index;
		}
	}
	return NULL;
}

static int send_error(int client_fd, int status, const char *message)
{
	struct http_response response;
	int result;

	http_response_init(&response);
	if (http_response_set(&response, status, "text/plain; charset=utf-8",
		message, strlen(message)) < 0) {
		return -1;
	}
	result = http_send_response(client_fd, &response);
	http_response_destroy(&response);
	return result;
}

static void handle_client(int client_fd, int public_dir_fd, const struct sockaddr_in *peer)
{
	char buffer[HTTP_MAX_REQUEST_SIZE + 1];
	char remote_address[INET_ADDRSTRLEN] = "unknown";
	struct http_request request;
	struct http_response response;
	struct timeval timeout = { .tv_sec = 5, .tv_usec = 0 };
	size_t used = 0;
	int status = 400;
	int parse_result;

	(void)setsockopt(client_fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
	while (used < HTTP_MAX_REQUEST_SIZE) {
		ssize_t count = recv(client_fd, buffer + used,
			HTTP_MAX_REQUEST_SIZE - used, 0);
		if (count < 0 && errno == EINTR) {
			continue;
		}
		if (count <= 0) {
			break;
		}
		used += (size_t)count;
		if (find_header_end(buffer, used) != NULL) {
			break;
		}
	}
	buffer[used] = '\0';
	if (find_header_end(buffer, used) == NULL) {
		if (used >= HTTP_MAX_REQUEST_SIZE) {
			status = 431;
			(void)send_error(client_fd, status, "Request Header Fields Too Large\n");
		} else if (used > 0) {
			(void)send_error(client_fd, status, "Bad Request\n");
		}
		goto log_request;
	}
	parse_result = http_parse_request(buffer, used, &request);
	if (parse_result != HTTP_PARSE_OK) {
		status = parse_result == HTTP_PARSE_TOO_LARGE ? 431 : 400;
		(void)send_error(client_fd, status,
			status == 431 ? "Request Header Fields Too Large\n" : "Bad Request\n");
		goto log_request;
	}
	http_response_init(&response);
	router_handle_request(public_dir_fd, &request, &response);
	status = response.status;
	(void)http_send_response(client_fd, &response);
	http_response_destroy(&response);

log_request:
	if (inet_ntop(AF_INET, &peer->sin_addr, remote_address, sizeof(remote_address)) == NULL) {
		strcpy(remote_address, "unknown");
	}
	printf("{\"level\":\"info\",\"event\":\"request\",\"remote\":\"%s:%u\",\"status\":%d}\n",
		remote_address, (unsigned int)ntohs(peer->sin_port), status);
	fflush(stdout);
}

int server_run(void)
{
	struct sockaddr_in address;
	struct sigaction action;
	int public_dir_fd;
	int server_fd;
	int reuse_address = 1;

	server_running = 1;
	memset(&action, 0, sizeof(action));
	action.sa_handler = stop_server;
	sigemptyset(&action.sa_mask);
	if (sigaction(SIGINT, &action, NULL) < 0 || sigaction(SIGTERM, &action, NULL) < 0) {
		perror("sigaction");
		return 1;
	}
	(void)signal(SIGPIPE, SIG_IGN);
	public_dir_fd = open("public", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
	if (public_dir_fd < 0) {
		perror("open public/");
		return 1;
	}
	server_fd = socket(AF_INET, SOCK_STREAM, 0);
	if (server_fd < 0) {
		perror("socket");
		close(public_dir_fd);
		return 1;
	}
	(void)setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR,
		&reuse_address, sizeof(reuse_address));
	memset(&address, 0, sizeof(address));
	address.sin_family = AF_INET;
	address.sin_port = htons(SERVER_PORT);
	address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
		perror("bind 127.0.0.1:8080");
		close(server_fd);
		close(public_dir_fd);
		return 1;
	}
	if (listen(server_fd, SERVER_BACKLOG) < 0) {
		perror("listen");
		close(server_fd);
		close(public_dir_fd);
		return 1;
	}
	printf("ARES listening on http://127.0.0.1:%d\n", SERVER_PORT);
	while (server_running) {
		struct sockaddr_in peer;
		socklen_t peer_length = sizeof(peer);
		int client_fd = accept(server_fd, (struct sockaddr *)&peer, &peer_length);

		if (client_fd < 0) {
			if (errno == EINTR) continue;
			if (server_running) perror("accept");
			break;
		}
		handle_client(client_fd, public_dir_fd, &peer);
		close(client_fd);
	}
	close(server_fd);
	close(public_dir_fd);
	return 0;
}