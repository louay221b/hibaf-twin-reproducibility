/*
 * HiBaF-Twin hardware timing harness (Raspberry Pi 4 / any Linux, and ESP32 under ESP-IDF).
 * Runs the self-test of the portable genus-2 implementation on the target, then times each
 * operation REPEAT times and prints median/min/max per operation as CSV lines:
 *   HW,<platform>,<operation>,<n>,<median_ms>,<min_ms>,<max_ms>,<repeats>,<ops_per_repeat>
 * Linux: wall clock (CLOCK_MONOTONIC_RAW). ESP32: esp_timer (1 us resolution, 64-bit).
 */
#include "g2.c"

#ifndef REPEAT
#define REPEAT 7
#endif
#ifndef MAXN_HW
#define MAXN_HW 500
#endif

#if defined(ESP_PLATFORM)
#include "esp_timer.h"
#include "mbedtls/gcm.h"
#include "esp_private/esp_clk.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
static double now_ms(void) { return esp_timer_get_time() / 1000.0; }   /* 64-bit microsecond timer, no wrap */
static const char *PLATFORM = "esp32";
static void yield_wdt(void) { vTaskDelay(1); }
#else
#include <time.h>
static double now_ms(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC_RAW, &t); return t.tv_sec * 1e3 + t.tv_nsec / 1e6; }
#if defined(__aarch64__)
static const char *PLATFORM = "aarch64";
#elif defined(__x86_64__)
static const char *PLATFORM = "x86_64";
#else
static const char *PLATFORM = "other";
#endif
static void yield_wdt(void) {}
#endif

static dv PTS[64];
static dv *TABS; static int8_t (*DG)[300]; static int *LEN; static sc *KS; static dv *DS; static dv BK[1 << 10];
static int msm_alloc(int m) {
    TABS = malloc(sizeof(dv) * (size_t)m * 8); DG = malloc(300 * (size_t)m); LEN = malloc(sizeof(int) * (size_t)m);
    KS = malloc(sizeof(sc) * (size_t)m); DS = malloc(sizeof(dv) * (size_t)m);
    return TABS && DG && LEN && KS && DS;
}
static void msm_free(void) { free(TABS); free(DG); free(LEN); free(KS); free(DS); }
static void msm_fill(int n, int short_coeff) {
    int m = 2*n + 1;
    for (int j = 0; j < m; j++) { int bits = (short_coeff && j >= 1 && j <= n) ? 128 : 254; sc_rand(&KS[j], bits); DS[j] = PTS[(j*7 + 3) % 64]; }
}
static int cmpd(const void *a, const void *b) { double x = *(const double *)a, y = *(const double *)b; return (x > y) - (x < y); }
static void report(const char *op, int n, double *t, int ops) {
    qsort(t, REPEAT, sizeof(double), cmpd);
    printf("HW,%s,%s,%d,%.6f,%.6f,%.6f,%d,%d\n", PLATFORM, op, n, t[REPEAT/2] / ops, t[0] / ops, t[REPEAT-1] / ops, REPEAT, ops);
}

#if defined(ESP_PLATFORM)
/*
 * Isolated AES-128-GCM timing benchmark: an 8-byte input and 160 bytes of AAD.
 * Measures a full encryption + tag generation (not a tag-only operation).
 * The fixed key/nonce and repeated identical plaintext are ONLY for timing;
 * real sensor reports must use unique nonces under a given GCM key.
 * Seven timed samples of 1000 calls each use the existing CSV report format.
 */
static void bench_gcm_tag(void) {
    mbedtls_gcm_context g;
    unsigned char key[16] = {0}, iv[12] = {0};
    unsigned char ad[160] = {0}, pt[8] = {0}, ct[8], tag[16];
    const int n = 1000;
    double elapsed_ms[REPEAT];
    mbedtls_gcm_init(&g);

    int rc = mbedtls_gcm_setkey(&g, MBEDTLS_CIPHER_ID_AES, key, 128);
    if (rc != 0) {
        printf("ERROR,esp32,gcm_tag_8B_ad160,setkey,%d\n", rc);
        mbedtls_gcm_free(&g);
        return;
    }

    for (int r = 0; r < REPEAT; ++r) {
        int64_t t0 = esp_timer_get_time();
        for (int i = 0; i < n; ++i) {
            rc = mbedtls_gcm_crypt_and_tag(
                &g, MBEDTLS_GCM_ENCRYPT, sizeof(pt),
                iv, sizeof(iv), ad, sizeof(ad),
                pt, ct, sizeof(tag), tag
            );
            if (rc != 0) break;
        }
        int64_t t1 = esp_timer_get_time();
        if (rc != 0) {
            printf("ERROR,esp32,gcm_tag_8B_ad160,encrypt,%d\n", rc);
            mbedtls_gcm_free(&g);
            return;
        }
        elapsed_ms[r] = (double)(t1 - t0) / 1000.0;
        yield_wdt();
    }

    report("gcm_tag_8B_ad160", 0, elapsed_ms, n);
    mbedtls_gcm_free(&g);
}
#endif

static int ilog2(int m) { int r = 0; while ((1 << (r+1)) <= m) r++; return r; }

static int selftest(void) {
    int bad = 0;
    for (int i = 0; i < 64; i++) { sc k; sc_rand(&k, 254); smul(&PTS[i], &k, &GEN, 4); }
    for (int i = 0; i < 100; i++) {
        dv A = PTS[rnd32() % 64], B = PTS[rnd32() % 64], R1, R2;
        dv_add(&R1, &A, &B); FORCE_GENERIC = 1; dv_add(&R2, &A, &B); FORCE_GENERIC = 0;
        if (!dv_eq(&R1, &R2) || !dv_on_curve(&R1)) bad++;
    }
    dv Z; smul(&Z, &ORDER_Q, &GEN, 4); bad += Z.deg != 0;
    sc k; memset(&k, 0, sizeof(k)); k.w[0] = 12345; k.w[6] = 1u << 8; dv R; smul(&R, &k, &GEN, 4);
    fe ref; fe_from_dec(&ref, "144174427563130030682890042837566160723"); bad += !fe_eq(&R.u0, &ref);
    printf("SELFTEST,%s,%s\n", PLATFORM, bad ? "FAIL" : "PASS");
    return bad;
}

static void bench_all(int maxn) {
    double t[REPEAT];
    fe a = PTS[0].u0, b = PTS[1].u1; dv x;
    for (int r = 0; r < REPEAT; r++) { double s = now_ms(); for (int i = 0; i < 2000; i++) fe_mul(&a, &a, &b); t[r] = now_ms() - s; }
    report("field_mul", 0, t, 2000);
    for (int r = 0; r < REPEAT; r++) { double s = now_ms(); for (int i = 0; i < 200; i++) { fe_inv(&a, &a); a.w[0] ^= 1; } t[r] = now_ms() - s; }
    report("field_inv", 0, t, 200);
    for (int r = 0; r < REPEAT; r++) { x = PTS[0]; double s = now_ms(); for (int i = 0; i < 200; i++) dv_add(&x, &x, &PTS[1 + (i & 31)]); t[r] = now_ms() - s; }
    report("group_add", 0, t, 200);
    for (int r = 0; r < REPEAT; r++) { x = PTS[0]; double s = now_ms(); for (int i = 0; i < 200; i++) dv_dbl(&x, &x); t[r] = now_ms() - s; }
    report("group_dbl", 0, t, 200); yield_wdt();
    for (int r = 0; r < REPEAT; r++) { sc k; sc_rand(&k, 254); double s = now_ms(); smul(&x, &k, &PTS[r % 64], 4); t[r] = now_ms() - s; yield_wdt(); }
    report("hecm", 0, t, 1);
    msm_alloc(2);
    for (int r = 0; r < REPEAT; r++) { sc_rand(&KS[0], 254); sc_rand(&KS[1], 254); DS[0] = PTS[r]; DS[1] = PTS[r + 9];
        double s = now_ms(); straus(&x, KS, DS, 2, 4, TABS, DG, LEN); t[r] = now_ms() - s; yield_wdt(); }
    report("indiv_verify", 1, t, 1); msm_free();
    int ns[] = {1, 5, 10, 25, 50, 100, 250, 500};
    for (unsigned i = 0; i < sizeof(ns)/sizeof(ns[0]); i++) {
        int n = ns[i], m = 2*n + 1; if (n > maxn) break;
        if (!msm_alloc(m)) { printf("OOM,%d\n", n); break; }
        for (int r = 0; r < REPEAT; r++) { msm_fill(n, 1); double s = now_ms(); straus(&x, KS, DS, m, m < 100 ? 4 : 5, TABS, DG, LEN); t[r] = now_ms() - s; yield_wdt(); }
        report("msm_straus_short", n, t, 1);
        if (m >= 21) {
            int c = ilog2(m) - 1; if (c < 2) c = 2;
            for (int r = 0; r < REPEAT; r++) { msm_fill(n, 0); double s = now_ms(); pippenger(&x, KS, DS, m, c, BK); t[r] = now_ms() - s; yield_wdt(); }
            report("msm_pippenger", n, t, 1);
        }
        msm_free();
    }
}

#if defined(ESP_PLATFORM)
void app_main(void) {
    setup();
    printf("HiBaF-Twin hardware benchmark, CPU %d MHz\n", (int)(esp_clk_cpu_freq() / 1000000));
    if (selftest()) { printf("DONE,FAIL\n"); return; }
    bench_all(50);
    bench_gcm_tag();
    printf("DONE\n");
}
#else
int main(int argc, char **argv) {
    setup();
    int maxn = argc > 1 ? atoi(argv[1]) : MAXN_HW;
    if (selftest()) return 1;
    bench_all(maxn);
    printf("DONE\n");
    return 0;
}
#endif
