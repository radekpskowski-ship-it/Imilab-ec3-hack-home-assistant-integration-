/* shbfprobe: print the 32-byte shbf header and the first NAL of each video message.
 * Usage: shbfprobe [/run/video_mainstream] [count] */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
void log_vdebug(const char *f, va_list ap) { fputs("[lib] ", stderr); vfprintf(stderr, f, ap); fputc(10, stderr); }
struct ev_loop;
struct ev_loop *ev_default_loop(unsigned int flags);
void ev_run(struct ev_loop *l, int flags);
void ev_break(struct ev_loop *l, int how);
void *shbfev_rcv_create(struct ev_loop *l, const char *path);
int shbfev_rcv_event(void *r, int type, void (*cb)(void *, void *, void *), void *ud);
int shbfev_rcv_start(void *r);
void shbf_free(void *b);
int shbf_get_size(void *b);
static int n, lim;
static void on_close(void *r, void *b, void *u) { puts("closed"); exit(1); }
static void on_msg(void *r, void *b, void *u) {
	unsigned char *p = b; int sz = shbf_get_size(b), i;
	printf("#%d size=%d hdr:", n, sz);
	for (i = 0; i < 64 && i < sz; i++) printf("%s%02x", i % 4 ? "" : " ", p[i]);
	for (i = 0; i + 4 < sz && i < 256; i++) if (!p[i] && !p[i+1] && !p[i+2] && p[i+3] == 1) { printf(" sc@%d nal=%02x", i, p[i+4]); break; }
	putchar('\n'); fflush(stdout);
	shbf_free(b);
	if (++n >= lim) exit(0);
}
int main(int c, char **v) {
	struct ev_loop *l = ev_default_loop(0); void *r;
	lim = c > 2 ? atoi(v[2]) : 30;
	r = shbfev_rcv_create(l, c > 1 ? v[1] : "/run/video_mainstream");
	if (!r) { puts("create fail"); return 1; }
	shbfev_rcv_event(r, 1, on_close, 0);
	shbfev_rcv_event(r, 2, on_msg, 0);
	shbfev_rcv_start(r);
	ev_run(l, 0);
	return 0;
}
