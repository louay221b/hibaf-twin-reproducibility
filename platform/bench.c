#include "g2.c"
#ifndef MAXN
#define MAXN 500
#endif
static dv PTS[64];
static void make_points(void) { for (int i = 0; i < 64; i++) { sc k; sc_rand(&k, 254); smul(&PTS[i], &k, &GEN, 4); } }
static void print_dv(const char *name, const dv *D) {
    printf("%s deg=%d u0=", name, D->deg); fe_print(&D->u0); printf(" u1="); fe_print(&D->u1);
    printf(" v0="); fe_print(&D->v0); printf(" v1="); fe_print(&D->v1); printf("\n");
}
/* MSM scratch */
static dv *TABS; static int8_t (*DG)[300]; static int *LEN; static sc *KS; static dv *DS;
#ifndef BKBITS
#define BKBITS 10
#endif
static dv BK[1 << BKBITS];
static void msm_alloc(int m) {
    TABS = malloc(sizeof(dv) * (size_t)m * 8); DG = malloc(300 * (size_t)m); LEN = malloc(sizeof(int) * (size_t)m);
    KS = malloc(sizeof(sc) * (size_t)m); DS = malloc(sizeof(dv) * (size_t)m);
    if (!TABS || !DG || !LEN || !KS || !DS) { printf("OOM m=%d\n", m); exit(1); }
}
static void msm_free(void) { free(TABS); free(DG); free(LEN); free(KS); free(DS); }
static int ilog2(int m) { int r = 0; while ((1 << (r+1)) <= m) r++; return r; }
/* fill coefficients: short=1 -> L full, n x 128-bit, n x 254-bit (verification structure) */
static void msm_fill(int n, int short_coeff) {
    int m = 2*n + 1;
    for (int j = 0; j < m; j++) {
        int bits = 254; if (short_coeff && j >= 1 && j <= n) bits = 128;
        sc_rand(&KS[j], bits); DS[j] = PTS[(j * 7 + 3) % 64];
    }
}
static unsigned long long c_mul, c_sqr, c_inv, c_add, c_dbl;
static void cnt_reset(void) { N_MUL = N_SQR = N_INV = N_GADD = N_GDBL = 0; }
static void cnt_print(const char *tag, int reps, uint32_t ticks) {
    printf("RESULT %s reps=%d fmul=%.1f fsqr=%.1f finv=%.2f gadd=%.1f gdbl=%.1f ticks=%u\n", tag, reps,
           (double)N_MUL/reps, (double)N_SQR/reps, (double)N_INV/reps, (double)N_GADD/reps, (double)N_GDBL/reps, (unsigned)ticks);
}
static int selftest(void) {
    int bad = 0; make_points();
    /* 1: fast path vs generic Cantor */
    for (int i = 0; i < 200; i++) {
        dv A = PTS[rnd32() % 64], B = PTS[rnd32() % 64], R1, R2, D1, D2;
        dv_add(&R1, &A, &B); FORCE_GENERIC = 1; dv_add(&R2, &A, &B); FORCE_GENERIC = 0;
        dv_dbl(&D1, &A);     FORCE_GENERIC = 1; dv_dbl(&D2, &A);     FORCE_GENERIC = 0;
        if (!dv_eq(&R1, &R2) || !dv_eq(&D1, &D2) || !dv_on_curve(&R1) || !dv_on_curve(&D1)) bad++;
        PTS[rnd32() % 64] = R1;
    }
    printf("CHECK fast_vs_generic_400_ops bad=%d\n", bad);
    /* 2: group order */
    dv Z; smul(&Z, &ORDER_Q, &GEN, 4); printf("CHECK qL_is_identity %s\n", Z.deg == 0 ? "PASS" : "FAIL"); bad += Z.deg != 0;
    for (int i = 0; i < 4; i++) { smul(&Z, &ORDER_Q, &PTS[i], 4); bad += Z.deg != 0; }
    printf("CHECK qP_is_identity_4_random %s\n", bad ? "FAIL" : "PASS");
    /* 3: MSM methods agree with sum of scalar multiplications */
    for (int n = 1; n <= 25; n += 12) {
        int m = 2*n + 1; msm_alloc(m); msm_fill(n, 1);
        dv ref; memset(&ref, 0, sizeof(ref));
        for (int j = 0; j < m; j++) { dv t; smul(&t, &KS[j], &DS[j], 4); dv_add(&ref, &ref, &t); }
        dv a, b, c; straus(&a, KS, DS, m, 4, TABS, DG, LEN); straus(&b, KS, DS, m, 5, TABS, DG, LEN);
        pippenger(&c, KS, DS, m, 4, BK);
        int ok = dv_eq(&a, &ref) && dv_eq(&b, &ref) && dv_eq(&c, &ref); bad += !ok;
        printf("CHECK msm_n%d straus_w4_w5_pippenger_equal %s\n", n, ok ? "PASS" : "FAIL"); msm_free();
    }
    /* 4: Schnorr-type batch equation with known discrete logs: sum alpha_i (s_i L + e_i P_i - U_i) = O
          constructed with s_i = u_i - e_i x_i mod q computed in Python is not available here, so we test
          linearity instead: (a)P + (b)P = (a+b)P with a+b < 2^256 */
    { sc a, b, ab; sc_rand(&a, 200); sc_rand(&b, 200); ab = a; uint64_t c = 0;
      for (int i = 0; i < SW; i++) { c += (uint64_t)ab.w[i] + b.w[i]; ab.w[i] = (uint32_t)c; c >>= 32; }
      dv x, y, z, s; smul(&x, &a, &PTS[5], 4); smul(&y, &b, &PTS[5], 4); smul(&z, &ab, &PTS[5], 4); dv_add(&s, &x, &y);
      printf("CHECK linearity %s\n", dv_eq(&s, &z) ? "PASS" : "FAIL"); bad += !dv_eq(&s, &z); }
    /* 5: vectors for Python cross-check: k*L for k = 2^200 + 12345 and k = q - 1 */
    { sc k; memset(&k, 0, sizeof(k)); k.w[0] = 12345; k.w[6] = 1u << 8; dv R; smul(&R, &k, &GEN, 4); print_dv("VEC k=2^200+12345", &R);
      k = ORDER_Q; k.w[0] -= 1; smul(&R, &k, &GEN, 4); print_dv("VEC k=q-1", &R); }
    printf("fallbacks_generic=%llu fast_add=%llu fast_dbl=%llu\n", N_GENERIC, N_FAST_ADD, N_FAST_DBL);
    printf("SELFTEST %s\n", bad ? "FAIL" : "PASS");
    return bad;
}
static void run(const char *mode, int n) {
    int reps; uint32_t t0, t1; cnt_reset();
    if (!strcmp(mode, "fmul")) { fe a = PTS[0].u0, b = PTS[1].u1; reps = 2000; t0 = tick(); for (int i = 0; i < reps; i++) fe_mul(&a, &a, &b); t1 = tick(); cnt_print("fmul", reps, t1-t0); if (a.w[0] == 7) puts(""); }
    else if (!strcmp(mode, "fadd")) { fe a = PTS[0].u0, b = PTS[1].u1; reps = 2000; t0 = tick(); for (int i = 0; i < reps; i++) fe_add(&a, &a, &b); t1 = tick(); cnt_print("fadd", reps, t1-t0); if (a.w[0] == 7) puts(""); }
    else if (!strcmp(mode, "finv")) { fe a = PTS[0].u0; reps = 200; t0 = tick(); for (int i = 0; i < reps; i++) { fe_inv(&a, &a); a.w[0] ^= 1; } t1 = tick(); cnt_print("finv", reps, t1-t0); }
    else if (!strcmp(mode, "gadd")) { dv a = PTS[0]; reps = 200; t0 = tick(); for (int i = 0; i < reps; i++) dv_add(&a, &a, &PTS[1 + (i & 31)]); t1 = tick(); N_GADD = reps; cnt_print("gadd", reps, t1-t0); }
    else if (!strcmp(mode, "gdbl")) { dv a = PTS[0]; reps = 200; t0 = tick(); for (int i = 0; i < reps; i++) dv_dbl(&a, &a); t1 = tick(); N_GDBL = reps; cnt_print("gdbl", reps, t1-t0); }
    else if (!strcmp(mode, "hecm")) { reps = 5; sc k[5]; for (int i = 0; i < reps; i++) sc_rand(&k[i], 254); dv R; t0 = tick(); for (int i = 0; i < reps; i++) smul(&R, &k[i], &PTS[i], 4); t1 = tick(); cnt_print("hecm", reps, t1-t0); }
    else if (!strcmp(mode, "indiv")) { reps = 5; msm_alloc(2); dv R; uint32_t tt = 0; for (int i = 0; i < reps; i++) { sc_rand(&KS[0], 254); sc_rand(&KS[1], 254); DS[0] = PTS[i]; DS[1] = PTS[i+9]; t0 = tick(); straus(&R, KS, DS, 2, 4, TABS, DG, LEN); tt += tick() - t0; } cnt_print("indiv", reps, tt); msm_free(); }
    else if (!strcmp(mode, "straus")) { int m = 2*n + 1; msm_alloc(m); msm_fill(n, 1); dv R; t0 = tick(); straus(&R, KS, DS, m, m < 100 ? 4 : 5, TABS, DG, LEN); t1 = tick(); char tg[32]; sprintf(tg, "straus_short_n%d", n); cnt_print(tg, 1, t1-t0); msm_free(); }
    else if (!strcmp(mode, "pipp")) { int m = 2*n + 1; msm_alloc(m); msm_fill(n, 0); int c = ilog2(m) - 1; if (c < 2) c = 2; dv R; t0 = tick(); pippenger(&R, KS, DS, m, c, BK); t1 = tick(); char tg[32]; sprintf(tg, "pippenger_n%d", n); cnt_print(tg, 1, t1-t0); msm_free(); }
    else if (!strcmp(mode, "none")) { cnt_print("none", 1, 0); }
}
int main(int argc, char **argv) {
    setup();
#ifdef ESP_ALL
    (void)argc; (void)argv;
    if (selftest()) { printf("SELFTEST FAILED\n"); }
    make_points();
    const char *ms[] = {"fmul","fadd","finv","gadd","gdbl","hecm","indiv"};
    for (unsigned i = 0; i < sizeof(ms)/sizeof(ms[0]); i++) run(ms[i], 0);
    int ns[] = {1, 5, 10, 25, 50};
    for (unsigned i = 0; i < sizeof(ns)/sizeof(ns[0]); i++) { run("straus", ns[i]); if (2*ns[i]+1 >= 21) run("pipp", ns[i]); }
    printf("DONE\n");
    return 0;
#else
    if (argc > 1 && !strcmp(argv[1], "selftest")) return selftest();
    make_points();
    if (argc > 1) run(argv[1], argc > 2 ? atoi(argv[2]) : 0);
    return 0;
#endif
}
