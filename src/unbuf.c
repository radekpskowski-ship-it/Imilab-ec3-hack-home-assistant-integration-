/* LD_PRELOAD: line-buffered stdout (miio_md prints events with printf into a pipe) */
#include <stdio.h>

__attribute__((constructor)) static void unbuf(void)
{
	setvbuf(stdout, NULL, _IOLBF, 0);
}
