#ifndef ARES_ROUTER_H
#define ARES_ROUTER_H

#include "http.h"

void router_handle_request(
	int public_dir_fd,
	const struct http_request *request,
	struct http_response *response);

#endif