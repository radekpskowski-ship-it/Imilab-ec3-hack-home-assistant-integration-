/* shbfdump: write the raw HEVC Annex-B payload of shbf video messages to stdout.
 * Usage: shbfdump [/run/video_mainstream] [count] > out.h265 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <unistd.h>
void log_vdebug(const char *f, va_list ap) { }
struct ev_loop;
struct ev_loop *ev_default_loop(unsigned int flags);
void ev_run(struct ev_loop *l, int flags);
void *shbfev_rcv_create(struct ev_loop *l, const char *path);
int shbfev_rcv_event(void *r, int type, void (*cb)(void *, void *, void *), void *ud);
int shbfev_rcv_start(void *r);
void shbf_free(void *b);
int shbf_get_size(void *b);
static int n, lim;
static void on_close(void *r, void *b, void *u) { exit(1); }
static void on_msg(void *r, void *b, void *u) {
	unsigned char *p = b; int sz = shbf_get_size(b);
	uint32_t len = p[16] | p[17] << 8 | p[18] << 16 | (uint32_t)p[19] << 24;
	if (sz > 32 && len <= (uint32_t)sz - 32) {
		fprintf(stderr, "#%d t=%u len=%u nal=%02x\n", n, p[0], len, p[36]);
		if (write(1, p + 32, len) < 0) exit(2);
	}
	shbf_free(b);
	if (++n >= lim) exit(0);
}
int main(int c, char **v) {
	struct ev_loop *l = ev_default_loop(0); void *r;
	lim = c > 2 ? atoi(v[2]) : 100;
	r = shbfev_rcv_create(l, c > 1 ? v[1] : "/run/video_mainstream");
	if (!r) return 1;
	shbfev_rcv_event(r, 1, on_close, 0);
	shbfev_rcv_event(r, 2, on_msg, 0);
	shbfev_rcv_start(r);
	ev_run(l, 0);
	return 0;
}
