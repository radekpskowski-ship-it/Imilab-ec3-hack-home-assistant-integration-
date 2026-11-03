/* mdprobe: dump /run/md_event messages (shbfev event type 3, like miio_md) */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
void log_vdebug(const char *f, va_list ap) { }
struct ev_loop;
struct ev_loop *ev_default_loop(unsigned int flags);
void ev_run(struct ev_loop *l, int flags);
void *shbfev_rcv_create(struct ev_loop *l, const char *path);
int shbfev_rcv_event(void *r, int type, void (*cb)(void *, void *, void *), void *ud);
int shbfev_rcv_start(void *r);
static int n, lim;
static void on_close(void *u, void *b, void *x) { puts("closed"); exit(1); }
static void on_msg(void *u, void *b, void *x)
{
	unsigned char *p = b;
	int i;

	printf("#%d x=%p(%d) ts=%lld :", n, x, (int)(intptr_t)x, *(long long *)p);
	for (i = 0; i < 96; i++)
		printf("%s%02x", i % 8 ? "" : " ", p[i]);
	putchar('\n');
	fflush(stdout);
	if (++n >= lim)
		exit(0);
}
int main(int c, char **v)
{
	struct ev_loop *l = ev_default_loop(0);
	void *r;

	lim = c > 1 ? atoi(v[1]) : 10;
	r = shbfev_rcv_create(l, "/run/md_event");
	if (!r)
		return 1;
	shbfev_rcv_event(r, 3, on_msg, 0);
	shbfev_rcv_event(r, 1, on_close, 0);
	shbfev_rcv_start(r);
	ev_run(l, 0);
	return 0;
}
