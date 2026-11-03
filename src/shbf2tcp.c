/* shbf2tcp — publishes the HEVC streams of fetch_av (shbf) as raw Annex-B over TCP.
 * Every client starts at the next key frame (VPS).
 * Slow client: pending bytes buffered up to MAXPEND, beyond that frames are skipped until the next IDR.
 * Usage: shbf2tcp [port_main] [port_sub]   (default 8001 8002) */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>

void log_vdebug(const char *f, va_list ap) { }
struct ev_loop;
struct ev_loop *ev_default_loop(unsigned int flags);
void ev_run(struct ev_loop *l, int flags);
void *shbfev_rcv_create(struct ev_loop *l, const char *path);
/* callback: cb(userdata, shbf_buf, ?) */
int shbfev_rcv_event(void *r, int type, void (*cb)(void *, void *, void *), void *ud);
int shbfev_rcv_start(void *r);
void shbf_free(void *b);
int shbf_get_size(void *b);

#define HDR 32
#define MAXCLI 4
#define MAXPEND (256 * 1024)

struct client {
	int fd, wait_key, plen;
	unsigned char *pend;
};

struct stream {
	const char *path;
	int lfd;
	unsigned rx, tx, skip;
	struct client cli[MAXCLI];
};

static struct stream streams[2] = {
	{ "/run/video_mainstream" },
	{ "/run/video_substream" },
};

static void drop(struct client *c)
{
	close(c->fd);
	free(c->pend);
	memset(c, 0, sizeof(*c));
	c->fd = -1;
}

static int listen_on(int port)
{
	struct sockaddr_in a;
	int one = 1, fd = socket(AF_INET, SOCK_STREAM, 0);

	if (fd < 0)
		return -1;
	setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
	memset(&a, 0, sizeof(a));
	a.sin_family = AF_INET;
	a.sin_port = htons(port);
	if (bind(fd, (struct sockaddr *)&a, sizeof(a)) || listen(fd, 4)) {
		perror("bind/listen");
		exit(1);
	}
	fcntl(fd, F_SETFL, O_NONBLOCK);
	return fd;
}

static void accept_new(struct stream *s)
{
	int fd, i, one = 1;

	while ((fd = accept(s->lfd, NULL, NULL)) >= 0) {
		for (i = 0; i < MAXCLI && s->cli[i].fd >= 0; i++)
			;
		if (i == MAXCLI) {
			close(fd);
			continue;
		}
		fcntl(fd, F_SETFL, O_NONBLOCK);
		setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
		s->cli[i].fd = fd;
		s->cli[i].wait_key = 1;
	}
}

/* Send as much as possible, buffer the rest. Returns -1 when the client must be dropped. */
static int send_buf(struct client *c, const unsigned char *p, int len)
{
	int n = 0;

	if (!c->plen) {
		n = send(c->fd, p, len, MSG_NOSIGNAL);
		if (n < 0) {
			if (errno != EAGAIN)
				return -1;
			n = 0;
		}
	}
	if (n < len) {
		if (c->plen + len - n > MAXPEND)
			return -1;
		c->pend = realloc(c->pend, c->plen + len - n);
		if (!c->pend)
			return -1;
		memcpy(c->pend + c->plen, p + n, len - n);
		c->plen += len - n;
	}
	return 0;
}

static int flush(struct client *c)
{
	int n;

	if (!c->plen)
		return 0;
	n = send(c->fd, c->pend, c->plen, MSG_NOSIGNAL);
	if (n < 0)
		return errno == EAGAIN ? 0 : -1;
	memmove(c->pend, c->pend + n, c->plen - n);
	c->plen -= n;
	return 0;
}

static void on_close(void *u, void *b, void *x)
{
	fprintf(stderr, "shbf2tcp: %s closed\n", ((struct stream *)u)->path);
	exit(1);
}

static void on_msg(void *u, void *b, void *x)
{
	struct stream *s = u;
	unsigned char *p = b;
	int sz = shbf_get_size(b), i, key;
	uint32_t len;

	accept_new(s);
	if (++s->rx % 200 == 0)
		fprintf(stderr, "%s: rx=%u tx=%u skip=%u\n", s->path, s->rx, s->tx, s->skip);
	if (sz <= HDR + 5)
		goto out;
	len = p[16] | p[17] << 8 | p[18] << 16 | (uint32_t)p[19] << 24;
	if (len > (uint32_t)sz - HDR)
		goto out;
	/* a key frame starts with a VPS (NAL type 32) */
	key = ((p[HDR + 4] >> 1) & 0x3f) == 32;
	for (i = 0; i < MAXCLI; i++) {
		struct client *c = &s->cli[i];

		if (c->fd < 0)
			continue;
		if (flush(c) < 0) {
			drop(c);
			continue;
		}
		if (c->wait_key && !key)
			continue;
		c->wait_key = 0;
		if (c->plen > MAXPEND / 2) {
			/* falling behind: skip until the next IDR */
			c->wait_key = 1;
			s->skip++;
			continue;
		}
		if (send_buf(c, p + HDR, len) < 0)
			drop(c);
		else
			s->tx++;
	}
out:
	shbf_free(b);
}

int main(int argc, char **argv)
{
	struct ev_loop *l = ev_default_loop(0);
	int i, j;

	signal(SIGPIPE, SIG_IGN);
	for (i = 0; i < 2; i++) {
		struct stream *s = &streams[i];
		void *r;

		for (j = 0; j < MAXCLI; j++)
			s->cli[j].fd = -1;
		s->lfd = listen_on(argc > i + 1 ? atoi(argv[i + 1]) : 8001 + i);
		r = shbfev_rcv_create(l, s->path);
		if (!r) {
			fprintf(stderr, "shbf2tcp: cannot open %s\n", s->path);
			return 1;
		}
		shbfev_rcv_event(r, 1, on_close, s);
		shbfev_rcv_event(r, 2, on_msg, s);
		shbfev_rcv_start(r);
	}
	ev_run(l, 0);
	return 0;
}
