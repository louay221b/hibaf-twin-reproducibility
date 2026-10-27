/*
 * Portable C genus-2 Jacobian arithmetic for HiBaF-Twin platform estimates.
 * Curve C: y^2 = x^5 + 8 over F_p, p = 2^127 - 2437; #J(F_p) = q prime (254 bits).
 * Mumford coordinates, affine. Common cases (deg 2 + deg 2, coprime; doubling of deg 2)
 * use closed-form composition with ONE field inversion; every other case falls back to
 * generic Cantor (polynomial xgcd), which is also used to cross-check the fast path.
 *
 * Limbs: 64-bit (LIMB64, needs unsigned __int128) or 32-bit (default on 32-bit targets).
 * Field inversion: binary extended Euclid (variable time; used for verification, which
 * handles public data) or Fermat (constant time, -DINV_FERMAT).
 * NOT constant-time overall (wNAF, branches): a deployment must harden signing.
 */
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(__SIZEOF_INT128__) && !defined(FORCE_LIMB32)
#define LIMB64 1
typedef uint64_t limb; typedef unsigned __int128 dlimb; enum { NL = 2, LB = 64 };
#else
typedef uint32_t limb; typedef uint64_t dlimb; enum { NL = 4, LB = 32 };
#endif

typedef struct { limb w[NL]; } fe;
#define CRED 2437u            /* p = 2^127 - CRED */

static fe FE_P;               /* p */
static void fe_set_p(void) {
    for (int i = 0; i < NL; i++) FE_P.w[i] = (limb)~(limb)0;
    FE_P.w[NL-1] >>= 1;                      /* 2^127 - 1 */
    FE_P.w[0] -= (CRED - 1);                 /* 2^127 - 2437 (no borrow: low limb is all ones) */
}
static inline int fe_iszero(const fe *a) { limb t = 0; for (int i = 0; i < NL; i++) t |= a->w[i]; return t == 0; }
static inline int fe_eq(const fe *a, const fe *b) { return memcmp(a, b, sizeof(fe)) == 0; }
static inline void fe_zero(fe *a) { memset(a, 0, sizeof(fe)); }
static inline void fe_small(fe *a, limb v) { fe_zero(a); a->w[0] = v; }
static inline int fe_geq_p(const fe *a) {
    for (int i = NL-1; i >= 0; i--) { if (a->w[i] > FE_P.w[i]) return 1; if (a->w[i] < FE_P.w[i]) return 0; }
    return 1;
}
static inline void raw_sub(fe *r, const fe *a, const fe *b, limb *borrow) {
    limb bw = 0;
    for (int i = 0; i < NL; i++) { dlimb t = (dlimb)a->w[i] - b->w[i] - bw; r->w[i] = (limb)t; bw = (limb)(t >> (2*LB-1)) & 1; }
    *borrow = bw;
}
static inline void raw_add(fe *r, const fe *a, const fe *b, limb *carry) {
    limb c = 0;
    for (int i = 0; i < NL; i++) { dlimb t = (dlimb)a->w[i] + b->w[i] + c; r->w[i] = (limb)t; c = (limb)(t >> LB); }
    *carry = c;
}
static inline void fe_add(fe *r, const fe *a, const fe *b) {   /* a,b < p < 2^127 -> sum < 2^128 */
    limb c; raw_add(r, a, b, &c);
    if (fe_geq_p(r)) { limb bw; raw_sub(r, r, &FE_P, &bw); }
}
static inline void fe_sub(fe *r, const fe *a, const fe *b) {
    limb bw; raw_sub(r, a, b, &bw);
    if (bw) { limb c; raw_add(r, r, &FE_P, &c); }
}
static inline void fe_neg(fe *r, const fe *a) { fe z; fe_zero(&z); fe_sub(r, &z, a); }

/* reduce a 2NL-limb product: 2^128 = 2*2437 (mod p), 2^127 = 2437 (mod p) */
static inline void fe_reduce(fe *r, const limb t[2*NL]) {
    limb x[NL]; dlimb c = 0;
    for (int i = 0; i < NL; i++) { c += (dlimb)t[i] + (dlimb)t[NL+i] * (2*CRED); x[i] = (limb)c; c >>= LB; }
    /* value = x + c*2^128, c < 2^14 ; fold bits >= 127 */
    limb hi = (limb)((x[NL-1] >> (LB-1)) | ((limb)c << 1));
    x[NL-1] &= ((limb)~(limb)0) >> 1;
    c = (dlimb)hi * CRED;
    for (int i = 0; i < NL; i++) { c += x[i]; x[i] = (limb)c; c >>= LB; }
    hi = x[NL-1] >> (LB-1); x[NL-1] &= ((limb)~(limb)0) >> 1;
    c = (dlimb)hi * CRED;
    for (int i = 0; i < NL; i++) { c += x[i]; x[i] = (limb)c; c >>= LB; }
    memcpy(r->w, x, sizeof(x));
    if (fe_geq_p(r)) { limb bw; raw_sub(r, r, &FE_P, &bw); }
}
static unsigned long long N_MUL, N_SQR, N_INV;  /* operation counters */
#if !defined(LIMB64) && !defined(GENERIC_MUL)
/* 32-bit targets: unrolled product scanning (Comba) with a 3-word accumulator */
#define MULACC(i, j) do { uint64_t pr = (uint64_t)a->w[i] * b->w[j]; uint64_t s = (uint64_t)c0 + (uint32_t)pr; c0 = (uint32_t)s; \
    s = (uint64_t)c1 + (uint32_t)(pr >> 32) + (uint32_t)(s >> 32); c1 = (uint32_t)s; c2 += (uint32_t)(s >> 32); } while (0)
#define COL_END(k) do { t[k] = c0; c0 = c1; c1 = c2; c2 = 0; } while (0)
static inline void fe_mul(fe *r, const fe *a, const fe *b) {
    uint32_t t[8], c0 = 0, c1 = 0, c2 = 0;
    MULACC(0,0); COL_END(0);
    MULACC(0,1); MULACC(1,0); COL_END(1);
    MULACC(0,2); MULACC(1,1); MULACC(2,0); COL_END(2);
    MULACC(0,3); MULACC(1,2); MULACC(2,1); MULACC(3,0); COL_END(3);
    MULACC(1,3); MULACC(2,2); MULACC(3,1); COL_END(4);
    MULACC(2,3); MULACC(3,2); COL_END(5);
    MULACC(3,3); COL_END(6);
    t[7] = c0;
    fe_reduce(r, t); N_MUL++;
}
#else
static inline void fe_mul(fe *r, const fe *a, const fe *b) {
    limb t[2*NL]; memset(t, 0, sizeof(t));
    for (int i = 0; i < NL; i++) {
        dlimb c = 0;
        for (int j = 0; j < NL; j++) { c += (dlimb)a->w[i] * b->w[j] + t[i+j]; t[i+j] = (limb)c; c >>= LB; }
        t[i+NL] = (limb)c;
    }
    fe_reduce(r, t); N_MUL++;
}
#endif
static inline void fe_sqr(fe *r, const fe *a) { fe_mul(r, a, a); N_MUL--; N_SQR++; }

static inline void halve_mod_p(fe *x) {      /* x <- x/2 mod p, x < p */
    limb top = 0;
    if (x->w[0] & 1) { limb c; raw_add(x, x, &FE_P, &c); top = c; }  /* x+p < 2^128, c = 0 */
    for (int i = 0; i < NL-1; i++) x->w[i] = (x->w[i] >> 1) | (x->w[i+1] << (LB-1));
    x->w[NL-1] = (x->w[NL-1] >> 1) | (top << (LB-1));
}
static inline int fe_is_one(const fe *a) { if (a->w[0] != 1) return 0; for (int i = 1; i < NL; i++) if (a->w[i]) return 0; return 1; }
static inline int fe_lt(const fe *a, const fe *b) {
    for (int i = NL-1; i >= 0; i--) { if (a->w[i] < b->w[i]) return 1; if (a->w[i] > b->w[i]) return 0; }
    return 0;
}
static void fe_inv(fe *r, const fe *a) {   /* a != 0 */
    N_INV++;
#ifdef INV_FERMAT
    /* a^(p-2), plain left-to-right square and multiply (constant pattern for fixed exponent) */
    fe e = FE_P; limb bw; fe two; fe_small(&two, 2); raw_sub(&e, &e, &two, &bw);
    fe acc; fe_small(&acc, 1);
    unsigned long long m0 = N_MUL, s0 = N_SQR;
    for (int i = 126; i >= 0; i--) {
        fe_sqr(&acc, &acc);
        if ((e.w[i / LB] >> (i % LB)) & 1) fe_mul(&acc, &acc, a);
    }
    N_MUL = m0; N_SQR = s0;   /* count inversion separately */
    *r = acc;
#else
    fe u = *a, v = FE_P, x1, x2; fe_small(&x1, 1); fe_zero(&x2);
    while (!fe_is_one(&u) && !fe_is_one(&v)) {
        while (!(u.w[0] & 1)) { for (int i = 0; i < NL-1; i++) u.w[i] = (u.w[i] >> 1) | (u.w[i+1] << (LB-1)); u.w[NL-1] >>= 1; halve_mod_p(&x1); }
        while (!(v.w[0] & 1)) { for (int i = 0; i < NL-1; i++) v.w[i] = (v.w[i] >> 1) | (v.w[i+1] << (LB-1)); v.w[NL-1] >>= 1; halve_mod_p(&x2); }
        limb bw;
        if (!fe_lt(&u, &v)) { raw_sub(&u, &u, &v, &bw); fe_sub(&x1, &x1, &x2); }
        else                { raw_sub(&v, &v, &u, &bw); fe_sub(&x2, &x2, &x1); }
    }
    *r = fe_is_one(&u) ? x1 : x2;
#endif
}
static void fe_from_dec(fe *r, const char *s) {
    fe_zero(r); fe ten; fe_small(&ten, 10);
    for (; *s; s++) { fe d; fe_small(&d, (limb)(*s - '0')); fe_mul(r, r, &ten); fe_add(r, r, &d); }
}
static void fe_print(const fe *a) {  /* decimal via repeated division by 10 on a copy */
    limb w[NL]; memcpy(w, a->w, sizeof(w)); char buf[64]; int n = 0;
    int nz; do {
        dlimb rem = 0; nz = 0;
        for (int i = NL-1; i >= 0; i--) { dlimb cur = (rem << LB) | w[i]; w[i] = (limb)(cur / 10); rem = cur % 10; if (w[i]) nz = 1; }
        buf[n++] = (char)('0' + (int)rem);
    } while (nz);
    while (n) putchar(buf[--n]);
}

/* ---------------- divisors ---------------- */
typedef struct { int deg; fe u0, u1, v0, v1; } dv;   /* u = x^2+u1x+u0 (deg 2) | x+u0 (deg 1) | 1 */
static fe F0;                                         /* f = x^5 + F0 */
static unsigned long long N_FAST_ADD, N_FAST_DBL, N_GENERIC;

/* ---------- generic polynomial arithmetic (fallback + cross-check) ---------- */
enum { MAXC = 16 };
typedef struct { int n; fe c[MAXC]; } poly;       /* n = number of coefficients after trimming */
static void p_trim(poly *a) { while (a->n > 0 && fe_iszero(&a->c[a->n-1])) a->n--; }
static void p_add(poly *r, const poly *a, const poly *b) {
    poly t; t.n = a->n > b->n ? a->n : b->n;
    for (int i = 0; i < t.n; i++) { fe x, y; if (i < a->n) x = a->c[i]; else fe_zero(&x); if (i < b->n) y = b->c[i]; else fe_zero(&y); fe_add(&t.c[i], &x, &y); }
    p_trim(&t); *r = t;
}
static void p_neg(poly *r, const poly *a) { poly t = *a; for (int i = 0; i < t.n; i++) fe_neg(&t.c[i], &a->c[i]); *r = t; }
static void p_sub(poly *r, const poly *a, const poly *b) { poly nb; p_neg(&nb, b); p_add(r, a, &nb); }
static void p_mul(poly *r, const poly *a, const poly *b) {
    poly t; if (!a->n || !b->n) { t.n = 0; *r = t; return; }
    t.n = a->n + b->n - 1; for (int i = 0; i < t.n; i++) fe_zero(&t.c[i]);
    for (int i = 0; i < a->n; i++) for (int j = 0; j < b->n; j++) { fe m; fe_mul(&m, &a->c[i], &b->c[j]); fe_add(&t.c[i+j], &t.c[i+j], &m); }
    p_trim(&t); *r = t;
}
static void p_divmod(poly *q, poly *r, const poly *a, const poly *b) {
    poly rr = *a, qq; p_trim(&rr); fe inv; fe_inv(&inv, &b->c[b->n-1]);
    qq.n = rr.n >= b->n ? rr.n - b->n + 1 : 0; for (int i = 0; i < qq.n; i++) fe_zero(&qq.c[i]);
    while (rr.n >= b->n && rr.n > 0) {
        fe c; fe_mul(&c, &rr.c[rr.n-1], &inv); int d = rr.n - b->n; qq.c[d] = c;
        for (int i = 0; i < b->n; i++) { fe m; fe_mul(&m, &c, &b->c[i]); fe_sub(&rr.c[d+i], &rr.c[d+i], &m); }
        p_trim(&rr);
    }
    p_trim(&qq); if (q) *q = qq; if (r) *r = rr;
}
static void p_monic(poly *a) { fe inv; fe_inv(&inv, &a->c[a->n-1]); for (int i = 0; i < a->n; i++) fe_mul(&a->c[i], &a->c[i], &inv); }
static void p_xgcd(poly *d, poly *s, poly *t, const poly *a, const poly *b) {
    poly r0 = *a, r1 = *b, s0, s1, t0, t1; p_trim(&r0); p_trim(&r1);
    s0.n = 1; fe_small(&s0.c[0], 1); s1.n = 0; t0.n = 0; t1.n = 1; fe_small(&t1.c[0], 1);
    while (r1.n) {
        poly q, r, tmp; p_divmod(&q, &r, &r0, &r1); r0 = r1; r1 = r;
        p_mul(&tmp, &q, &s1); p_sub(&tmp, &s0, &tmp); s0 = s1; s1 = tmp;
        p_mul(&tmp, &q, &t1); p_sub(&tmp, &t0, &tmp); t0 = t1; t1 = tmp;
    }
    fe inv; fe_inv(&inv, &r0.c[r0.n-1]);
    for (int i = 0; i < r0.n; i++) fe_mul(&r0.c[i], &r0.c[i], &inv);
    for (int i = 0; i < s0.n; i++) fe_mul(&s0.c[i], &s0.c[i], &inv);
    for (int i = 0; i < t0.n; i++) fe_mul(&t0.c[i], &t0.c[i], &inv);
    *d = r0; *s = s0; *t = t0;
}
static void dv_to_poly(poly *u, poly *v, const dv *D) {
    if (D->deg == 0) { u->n = 1; fe_small(&u->c[0], 1); v->n = 0; return; }
    if (D->deg == 1) { u->n = 2; u->c[0] = D->u0; fe_small(&u->c[1], 1); v->n = 1; v->c[0] = D->v0; p_trim(v); return; }
    u->n = 3; u->c[0] = D->u0; u->c[1] = D->u1; fe_small(&u->c[2], 1);
    v->n = 2; v->c[0] = D->v0; v->c[1] = D->v1; p_trim(v);
}
static void poly_to_dv(dv *D, const poly *u, const poly *v) {
    memset(D, 0, sizeof(*D)); D->deg = u->n - 1;
    if (D->deg >= 1) D->u0 = u->c[0];
    if (D->deg == 2) D->u1 = u->c[1];
    if (v->n >= 1) D->v0 = v->c[0];
    if (v->n >= 2) D->v1 = v->c[1];
}
static void dv_add_generic(dv *R, const dv *A, const dv *B) {
    N_GENERIC++;
    poly u1, v1, u2, v2, f; dv_to_poly(&u1, &v1, A); dv_to_poly(&u2, &v2, B);
    f.n = 6; for (int i = 0; i < 6; i++) fe_zero(&f.c[i]); f.c[0] = F0; fe_small(&f.c[5], 1);
    poly d1, e1, e2, d, c1, s3, s1, s2, tmp, tmp2, u, v, num;
    p_xgcd(&d1, &e1, &e2, &u1, &u2);
    p_add(&tmp, &v1, &v2); p_xgcd(&d, &c1, &s3, &d1, &tmp);
    p_mul(&s1, &c1, &e1); p_mul(&s2, &c1, &e2);
    p_mul(&tmp, &u1, &u2); p_mul(&tmp2, &d, &d); p_divmod(&u, NULL, &tmp, &tmp2);
    p_mul(&tmp, &s1, &u1); p_mul(&tmp, &tmp, &v2);
    p_mul(&tmp2, &s2, &u2); p_mul(&tmp2, &tmp2, &v1); p_add(&num, &tmp, &tmp2);
    p_mul(&tmp, &v1, &v2); p_add(&tmp, &tmp, &f); p_mul(&tmp, &s3, &tmp); p_add(&num, &num, &tmp);
    p_divmod(&tmp, NULL, &num, &d);
    if (u.n > 2) p_divmod(NULL, &v, &tmp, &u); else v.n = 0;
    while (u.n - 1 > 2) {
        p_mul(&tmp, &v, &v); p_sub(&tmp, &f, &tmp); p_divmod(&u, NULL, &tmp, &u);
        p_neg(&tmp, &v); p_divmod(NULL, &v, &tmp, &u);
    }
    p_monic(&u);
    if (u.n > 1) { poly vv; p_divmod(NULL, &vv, &v, &u); v = vv; } else v.n = 0;
    poly_to_dv(R, &u, &v);
}

/* ---------- fast paths ---------- */
/* k = (f - v^2)/u for u = x^2+a1x+a0, v = b1x+b0, f = x^5+F0 : k = x^3 + k2x^2 + k1x + k0 */
static inline void kpoly(fe *k2, fe *k1, fe *k0, const fe *a1, const fe *a0, const fe *b1) {
    fe t, a1s; fe_neg(k2, a1);
    fe_sqr(&a1s, a1); fe_sub(k1, &a1s, a0);
    /* k0 = -b1^2 + 2 a0 a1 - a1^3 */
    fe_mul(&t, a0, a1); fe_add(&t, &t, &t);
    fe a13; fe_mul(&a13, &a1s, a1); fe_sub(&t, &t, &a13);
    fe b1s; fe_sqr(&b1s, b1); fe_sub(k0, &t, &b1s);
}
/* finish composition: given s = s1x+s0 (actual), inv_s1 = 1/s1, base divisor (a1,a0,b1,b0) = (u1,v1),
   k = (f-v1^2)/u1, divisor w = (c1,c0) used for exact division: u3 ~ (k - s(l+2v1)) / w */
static inline void compose_finish(dv *R, const fe *s1, const fe *s0, const fe *inv_s1,
                                  const fe *a1, const fe *a0, const fe *b1, const fe *b0,
                                  const fe *k2, const fe *k1, const fe *c1, const fe *c0) {
    fe l2, l1, l0, t, m2, m1;
    /* l = s*u1 = s1x^3 + (s1a1+s0)x^2 + (s1a0+s0a1)x + s0a0 */
    fe_mul(&l2, s1, a1); fe_add(&l2, &l2, s0);
    fe_mul(&l1, s1, a0); fe_mul(&t, s0, a1); fe_add(&l1, &l1, &t);
    fe_mul(&l0, s0, a0);
    /* m = l + 2v1 : m3 = s1, m2 = l2, m1 = l1 + 2b1 */
    m2 = l2; fe_add(&m1, &l1, b1); fe_add(&m1, &m1, b1);
    /* num = k - s*m ; num4 = -s1^2 ; num3 = 1 - (s1 m2 + s0 s1) ; num2 = k2 - (s1 m1 + s0 m2) */
    fe n4, n3, n2, one; fe_small(&one, 1);
    fe_sqr(&n4, s1); fe_neg(&n4, &n4);
    fe_add(&t, &m2, s0); fe_mul(&t, &t, s1); fe_sub(&n3, &one, &t);
    fe t2; fe_mul(&t, s1, &m1); fe_mul(&t2, s0, &m2); fe_add(&t, &t, &t2); fe_sub(&n2, k2, &t);
    (void)k1;
    /* q = num / (x^2 + c1 x + c0): q2 = n4, q1 = n3 - c1 q2, q0 = n2 - c1 q1 - c0 q2 */
    fe q1, q0; fe_mul(&t, c1, &n4); fe_sub(&q1, &n3, &t);
    fe_mul(&t, c1, &q1); fe_sub(&q0, &n2, &t); fe_mul(&t, c0, &n4); fe_sub(&q0, &q0, &t);
    /* monic: multiply by 1/q2 = -(1/s1)^2 */
    fe iq; fe_sqr(&iq, inv_s1); fe_neg(&iq, &iq);
    fe U1, U0; fe_mul(&U1, &q1, &iq); fe_mul(&U0, &q0, &iq);
    /* v3 = -(l + v1) mod u3 ; e3 = s1, e2 = l2, e1 = l1 + b1, e0 = l0 + b0 */
    fe e1, e0; fe_add(&e1, &l1, b1); fe_add(&e0, &l0, b0);
    fe U1s, x3c1, x3c0;               /* x^3 = (U1^2 - U0) x + U1 U0 */
    fe_sqr(&U1s, &U1); fe_sub(&x3c1, &U1s, &U0); fe_mul(&x3c0, &U1, &U0);
    fe V1, V0;
    fe_mul(&V1, s1, &x3c1); fe_mul(&t, &l2, &U1); fe_sub(&V1, &V1, &t); fe_add(&V1, &V1, &e1); fe_neg(&V1, &V1);
    fe_mul(&V0, s1, &x3c0); fe_mul(&t, &l2, &U0); fe_sub(&V0, &V0, &t); fe_add(&V0, &V0, &e0); fe_neg(&V0, &V0);
    R->deg = 2; R->u1 = U1; R->u0 = U0; R->v1 = V1; R->v0 = V0;
}
static int FORCE_GENERIC = 0;
static void dv_dbl(dv *R, const dv *D);
static void dv_add(dv *R, const dv *A, const dv *B) {
    if (A->deg == 0) { *R = *B; return; }
    if (B->deg == 0) { *R = *A; return; }
    if (FORCE_GENERIC || A->deg != 2 || B->deg != 2) { dv_add_generic(R, A, B); return; }
    if (fe_eq(&A->u0, &B->u0) && fe_eq(&A->u1, &B->u1)) {
        if (fe_eq(&A->v0, &B->v0) && fe_eq(&A->v1, &B->v1)) { dv_dbl(R, A); return; }
        dv_add_generic(R, A, B); return;
    }
    const fe *a1 = &A->u1, *a0 = &A->u0, *b1 = &A->v1, *b0 = &A->v0;
    const fe *c1 = &B->u1, *c0 = &B->u0;
    fe z1, z0, i1, i0, r, t, t2;
    fe_sub(&z1, a1, c1); fe_sub(&z0, a0, c0);
    fe_neg(&i1, &z1); fe_mul(&t, &z1, c1); fe_sub(&i0, &z0, &t);
    /* r = z0^2 - z0 z1 c1 + z1^2 c0 = z0*i0 + z1^2 c0 */
    fe_mul(&r, &z0, &i0); fe_sqr(&t, &z1); fe_mul(&t, &t, c0); fe_add(&r, &r, &t);
    fe w1, w0; fe_sub(&w1, &B->v1, b1); fe_sub(&w0, &B->v0, b0);
    /* s'' = w * i mod u2 */
    fe w1i1, S1, S0;
    fe_mul(&w1i1, &w1, &i1);
    fe_mul(&S1, &w1, &i0); fe_mul(&t, &w0, &i1); fe_add(&S1, &S1, &t); fe_mul(&t, &w1i1, c1); fe_sub(&S1, &S1, &t);
    fe_mul(&S0, &w0, &i0); fe_mul(&t, &w1i1, c0); fe_sub(&S0, &S0, &t);
    if (fe_iszero(&r) || fe_iszero(&S1)) { dv_add_generic(R, A, B); return; }
    N_FAST_ADD++;
    fe inv, rinv, invs1, s1, s0;
    fe_mul(&t, &r, &S1); fe_inv(&inv, &t);
    fe_mul(&rinv, &inv, &S1);                     /* 1/r */
    fe_sqr(&t2, &r); fe_mul(&invs1, &inv, &t2);   /* 1/s1 = r/S1 = inv * r^2 */
    fe_mul(&s1, &S1, &rinv); fe_mul(&s0, &S0, &rinv);
    fe k2, k1, k0; kpoly(&k2, &k1, &k0, a1, a0, b1);
    compose_finish(R, &s1, &s0, &invs1, a1, a0, b1, b0, &k2, &k1, c1, c0);
}
static void dv_dbl(dv *R, const dv *D) {
    if (D->deg == 0) { *R = *D; return; }
    if (FORCE_GENERIC || D->deg != 2) { dv_add_generic(R, D, D); return; }
    const fe *a1 = &D->u1, *a0 = &D->u0, *b1 = &D->v1, *b0 = &D->v0;
    fe k2, k1, k0, t, t2; kpoly(&k2, &k1, &k0, a1, a0, b1);
    /* k mod u : kr1 = (a1^2 - a0) - k2 a1 + k1 ; kr0 = a1 a0 - k2 a0 + k0 */
    fe kr1, kr0;
    fe_sqr(&kr1, a1); fe_sub(&kr1, &kr1, a0); fe_mul(&t, &k2, a1); fe_sub(&kr1, &kr1, &t); fe_add(&kr1, &kr1, &k1);
    fe_mul(&kr0, a1, a0); fe_mul(&t, &k2, a0); fe_sub(&kr0, &kr0, &t); fe_add(&kr0, &kr0, &k0);
    /* inverse of z = 2v mod u */
    fe z1, z0, i1, i0, r;
    fe_add(&z1, b1, b1); fe_add(&z0, b0, b0);
    fe_neg(&i1, &z1); fe_mul(&t, &z1, a1); fe_sub(&i0, &z0, &t);
    fe_mul(&r, &z0, &i0); fe_sqr(&t, &z1); fe_mul(&t, &t, a0); fe_add(&r, &r, &t);
    fe w1i1, S1, S0;
    fe_mul(&w1i1, &kr1, &i1);
    fe_mul(&S1, &kr1, &i0); fe_mul(&t, &kr0, &i1); fe_add(&S1, &S1, &t); fe_mul(&t, &w1i1, a1); fe_sub(&S1, &S1, &t);
    fe_mul(&S0, &kr0, &i0); fe_mul(&t, &w1i1, a0); fe_sub(&S0, &S0, &t);
    if (fe_iszero(&r) || fe_iszero(&S1)) { dv_add_generic(R, D, D); return; }
    N_FAST_DBL++;
    fe inv, rinv, invs1, s1, s0;
    fe_mul(&t, &r, &S1); fe_inv(&inv, &t);
    fe_mul(&rinv, &inv, &S1); fe_sqr(&t2, &r); fe_mul(&invs1, &inv, &t2);
    fe_mul(&s1, &S1, &rinv); fe_mul(&s0, &S0, &rinv);
    compose_finish(R, &s1, &s0, &invs1, a1, a0, b1, b0, &k2, &k1, a1, a0);
}
static inline void dv_neg(dv *R, const dv *D) { *R = *D; if (D->deg >= 1) fe_neg(&R->v0, &D->v0); if (D->deg == 2) fe_neg(&R->v1, &D->v1); }
static inline int dv_eq(const dv *A, const dv *B) {
    if (A->deg != B->deg) return 0; if (A->deg == 0) return 1;
    if (!fe_eq(&A->u0, &B->u0) || !fe_eq(&A->v0, &B->v0)) return 0;
    if (A->deg == 2 && (!fe_eq(&A->u1, &B->u1) || !fe_eq(&A->v1, &B->v1))) return 0;
    return 1;
}
static int dv_on_curve(const dv *D) {   /* u | f - v^2 */
    if (D->deg == 0) return 1;
    poly u, v, f, t, r; dv_to_poly(&u, &v, D);
    f.n = 6; for (int i = 0; i < 6; i++) fe_zero(&f.c[i]); f.c[0] = F0; fe_small(&f.c[5], 1);
    p_mul(&t, &v, &v); p_sub(&t, &f, &t); p_divmod(NULL, &r, &t, &u); return r.n == 0;
}

/* ---------------- scalars and scalar multiplication ---------------- */
enum { SW = 9 };                          /* 9 x 32-bit words: 288 bits */
typedef struct { uint32_t w[SW]; } sc;
static int sc_iszero(const sc *k) { for (int i = 0; i < SW; i++) if (k->w[i]) return 0; return 1; }
static void sc_addsmall(sc *k, int32_t d) {   /* k += d (d may be negative), no underflow by construction */
    int64_t c = d;
    for (int i = 0; i < SW && c; i++) { int64_t t = (int64_t)k->w[i] + c; k->w[i] = (uint32_t)t; c = t >> 32; }
}
static void sc_shr1(sc *k) { for (int i = 0; i < SW-1; i++) k->w[i] = (k->w[i] >> 1) | (k->w[i+1] << 31); k->w[SW-1] >>= 1; }
static int wnaf(int8_t *out, sc k, int w) {
    int n = 0;
    while (!sc_iszero(&k)) {
        int d = 0;
        if (k.w[0] & 1) { d = (int)(k.w[0] & ((1u << w) - 1)); if (d >= (1 << (w-1))) d -= (1 << w); sc_addsmall(&k, -d); }
        out[n++] = (int8_t)d; sc_shr1(&k);
    }
    return n;
}
enum { MAXTAB = 16 };   /* up to w = 6 */
static void precompute_odd(dv *tbl, const dv *D, int w) {
    dv D2; dv_dbl(&D2, D); tbl[0] = *D;
    for (int i = 1; i < (1 << (w-2)); i++) dv_add(&tbl[i], &tbl[i-1], &D2);
}
static unsigned long long N_GADD, N_GDBL;
static void smul(dv *R, const sc *k, const dv *D, int w) {
    dv tbl[MAXTAB]; int8_t dg[300]; precompute_odd(tbl, D, w); int n = wnaf(dg, *k, w);
    dv acc; memset(&acc, 0, sizeof(acc));
    for (int i = n-1; i >= 0; i--) {
        dv_dbl(&acc, &acc); N_GDBL++;
        if (dg[i] > 0) { dv_add(&acc, &acc, &tbl[dg[i] >> 1]); N_GADD++; }
        else if (dg[i] < 0) { dv t; dv_neg(&t, &tbl[(-dg[i]) >> 1]); dv_add(&acc, &acc, &t); N_GADD++; }
    }
    *R = acc;
}
/* interleaved wNAF (Straus) MSM; tables allocated by caller-provided scratch */
static void straus(dv *R, const sc *ks, const dv *Ds, int m, int w, dv *tabs, int8_t (*dg)[300], int *len) {
    int T = 1 << (w-2), nb = 0;
    for (int j = 0; j < m; j++) { precompute_odd(&tabs[j*T], &Ds[j], w); len[j] = wnaf(dg[j], ks[j], w); if (len[j] > nb) nb = len[j]; }
    dv acc; memset(&acc, 0, sizeof(acc));
    for (int b = nb-1; b >= 0; b--) {
        dv_dbl(&acc, &acc); N_GDBL++;
        for (int j = 0; j < m; j++) if (b < len[j] && dg[j][b]) {
            int d = dg[j][b];
            if (d > 0) dv_add(&acc, &acc, &tabs[j*T + (d >> 1)]);
            else { dv t; dv_neg(&t, &tabs[j*T + ((-d) >> 1)]); dv_add(&acc, &acc, &t); }
            N_GADD++;
        }
    }
    *R = acc;
}
static void pippenger(dv *R, const sc *ks, const dv *Ds, int m, int c, dv *bk) {
    int nbits = 256; dv acc; memset(&acc, 0, sizeof(acc));
    int nw = (nbits + c - 1) / c;
    for (int win = nw-1; win >= 0; win--) {
        for (int i = 0; i < c; i++) { dv_dbl(&acc, &acc); N_GDBL++; }
        int nbk = 1 << c; for (int i = 0; i < nbk; i++) bk[i].deg = -1;
        for (int j = 0; j < m; j++) {
            int bit = win * c, idx = 0;
            for (int t = 0; t < c; t++) { int bb = bit + t; if (bb < 32*SW && ((ks[j].w[bb >> 5] >> (bb & 31)) & 1)) idx |= 1 << t; }
            if (idx) { if (bk[idx].deg < 0) bk[idx] = Ds[j]; else { dv_add(&bk[idx], &bk[idx], &Ds[j]); N_GADD++; } }
        }
        dv run, sum; memset(&run, 0, sizeof(run)); memset(&sum, 0, sizeof(sum));
        for (int idx = nbk-1; idx > 0; idx--) {
            if (bk[idx].deg >= 0) { dv_add(&run, &run, &bk[idx]); N_GADD++; }
            dv_add(&sum, &sum, &run); N_GADD++;
        }
        dv_add(&acc, &acc, &sum); N_GADD++;
    }
    *R = acc;
}

/* ---------------- deterministic RNG ---------------- */
static uint64_t rs = 0x9E3779B97F4A7C15ull;
static uint32_t rnd32(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return (uint32_t)(rs >> 16); }
static void sc_rand(sc *k, int bits) { memset(k, 0, sizeof(*k)); for (int i = 0; i < (bits + 31)/32; i++) k->w[i] = rnd32(); if (bits % 32) k->w[(bits-1)/32] &= (1u << (bits % 32)) - 1; }

/* ---------------- platform timer ---------------- */
#if defined(__XTENSA__)
static inline uint32_t tick(void) { uint32_t c; __asm__ volatile("rsr.ccount %0" : "=a"(c)); return c; }
#else
static inline uint32_t tick(void) { return 0; }
#endif

static dv GEN;
static void setup(void) {
    fe_set_p(); fe_small(&F0, 8);
    GEN.deg = 2;
    fe_from_dec(&GEN.u0, "5");
    fe_from_dec(&GEN.u1, "170141183460469231731687303715884103285");
    fe_from_dec(&GEN.v0, "116971162961552598598503687657478593753");
    fe_from_dec(&GEN.v1, "53170020498916633133183616058405509541");
}
static const sc ORDER_Q = {{0x807ec86du, 0x75ce434bu, 0x108f1627u, 0x7ea2e5f9u, 0xb26e3f04u, 0x6127c86cu, 0xffffffffu, 0x3fffffffu, 0x00000000u}};
