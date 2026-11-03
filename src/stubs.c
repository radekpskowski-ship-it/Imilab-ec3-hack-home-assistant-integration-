/* Link-time stubs for the camera's proprietary libraries (libshbf, libshbfev, libev).
 * They only provide matching SONAMEs and symbols so the tools can be linked without
 * redistributing vendor code; on the camera the original /mnt/data/lib/*.so are used. */
struct ev_loop;
#ifdef STUB_EV
struct ev_loop *ev_default_loop(unsigned int flags) { return 0; }
void ev_run(struct ev_loop *l, int flags) { }
#endif
#ifdef STUB_SHBF
void shbf_free(void *b) { }
int shbf_get_size(void *b) { return 0; }
#endif
#ifdef STUB_SHBFEV
void *shbfev_rcv_create(struct ev_loop *l, const char *path) { return 0; }
int shbfev_rcv_event(void *r, int type, void (*cb)(void *, void *, void *), void *ud) { return 0; }
int shbfev_rcv_start(void *r) { return 0; }
#endif
