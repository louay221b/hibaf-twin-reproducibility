/*
 * HiBaF v2 network simulation for ns-3.49 (MSM-native secure reporting for IoT digital twins).
 *
 * Topology : P ponds; each pond = 1 collector + n sensors on its own IEEE 802.15.4 (2.4 GHz
 *            O-QPSK, 250 kb/s) channel with 6LoWPAN/IPv6/UDP; collectors and the site station
 *            on a 100 Mb/s CSMA LAN (IPv4/TCP); station -> back end (BE, digital twin) over a
 *            point-to-point WAN link (IPv4/TCP) with configurable rate, delay, loss, outages.
 * Protocol : authenticated window beacons (station -> collectors -> sensor broadcast, repeated),
 *            sensor reports with real HiBaF v2 byte sizes, collector link-MAC pre-filter,
 *            window/replay/quota/negative-cache checks, signature verification, container
 *            signing, station container verification + site container, BE AEAD + theta audit,
 *            DT commit, misbehaviour notice -> TTP revocation push.
 * Crypto   : NOT executed. Each cryptographic step is a calibrated CPU delay on a single-server
 *            FIFO CPU per node. Scalar-multiplication times are the authors' platform values
 *            (ESP32 28.62 ms, RPi4 4.20 ms); MSM/individual costs are ratios measured on a
 *            genus-2 Jacobian over F_(2^127-1) (bench_g2_127.json). Invalid-report isolation
 *            cost is computed from the ACTUAL validity pattern of each batch.
 * Variants : msm   (HiBaF v2: MSM everywhere + adaptive batch controller)          [proposed]
 *            msmfix(MSM, fixed flush batching, recursive bisection)                 [ablation]
 *            base  (no MSM: (2b+1) independent scalar mults, recursive bisection)   [ablation, = manuscript Base]
 *            ind   (conventional per-report Schnorr verification, theta = 1)        [baseline]
 *            sym   (hop-by-hop AEAD, collectors trusted, no signatures)             [weaker-security reference]
 */
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/csma-module.h"
#include "ns3/internet-module.h"
#include "ns3/lr-wpan-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/propagation-module.h"
#include "ns3/sixlowpan-module.h"
#include "ns3/spectrum-module.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <deque>
#include <fstream>
#include <map>
#include <memory>
#include <numeric>
#include <set>
#include <vector>

using namespace ns3;

// ------------------------------------------------------------------------------------- config
struct Cfg
{
    std::string variant = "msm";
    uint32_t nSensors = 100, perPond = 25;
    double reportInterval = 10.0, window = 30.0, simTime = 330.0, warmup = 30.0, drain = 15.0;
    double theta = 0.25, radius = 25.0, deadline = 2.0;
    uint32_t beaconRepeats = 3;
    double beaconSpacing = 0.15;
    std::string wanRate = "10Mbps";
    double wanDelayMs = 40, wanLoss = 0.0;
    double wanOutageStart = -1, wanOutageDur = 0;
    double maxWait = 0.1, stationFlush = 0.1, budgetTime = 1.0, grace = 2.0;
    // attacks
    double quotaMinInterval = -1; // fastest legitimate report interval for the quota (<0: reportInterval)
    uint32_t attackers = 0;
    double attackRate = 0.1, attackStart = 60;
    bool defenses = true; // negative cache + quota + revocation
    double outsiderRate = 0.0;
    bool evidence = true;          // revocation requires BE-validated evidence (GCM check)
    double byzNoticeRate = 0.0;    // false accusations/s sent by Byzantine collector 0
    bool sharedChannel = false;    // all ponds on one 802.15.4 channel
    double pondSpacing = 100.0;    // m between pond centres when sharedChannel
    double beaconStagger = 0.0;    // s; collector p rebroadcasts beacons p*beaconStagger later
    // bursts
    double burstStart = -1, burstDur = 0, burstInterval = 1.0;
    // platform (ms) — authors' measured scalar-multiplication times; BE value is an assumption
    double tHecmSensor = 28.62, tHecmCol = 4.20, tHecmSt = 4.20, tHecmBe = 0.10;
    double tAeadSensor = 0.075, tHashSensor = 0.0174, tHashCol = 0.0024, tAeadBe = 0.002;
    uint32_t run = 1;
    std::string out = "results";
    std::string tag = "";
    bool perReport = false;
};
static Cfg C;

// ------------------------------------------------------------------- cost model (HECM units)
static const double C_IND_MSM = 1.152;      // 2-term Straus (Shamir) verification, measured ratio
static const double C_IND_BASE = 2.0;       // two independent scalar mults (manuscript Base model)
static const double ADD_OVER_HECM = 0.0043; // measured T_add / T_HECM
static const std::vector<std::pair<double, double>> MSM_PTS = {
    {3, 1.19}, {11, 2.25}, {21, 5.05}, {51, 9.08}, {101, 15.75}, {201, 32.43}, {501, 80.69}, {1001, 171.69}};
static double
CMsm(double m)
{
    if (m <= MSM_PTS[0].first)
        return MSM_PTS[0].second * m / MSM_PTS[0].first;
    for (size_t i = 1; i < MSM_PTS.size(); ++i)
        if (m <= MSM_PTS[i].first)
        {
            auto [m0, c0] = MSM_PTS[i - 1];
            auto [m1, c1] = MSM_PTS[i];
            return c0 + (c1 - c0) * (m - m0) / (m1 - m0);
        }
    return MSM_PTS.back().second * m / MSM_PTS.back().first;
}
static bool UsesMsm() { return C.variant == "msm" || C.variant == "msmfix"; }
static double
BatchTest(uint32_t b) // cost of ONE randomized batch test over b signatures
{
    if (b == 1)
        return UsesMsm() || C.variant == "ind" ? C_IND_MSM : C_IND_BASE;
    if (UsesMsm())
        return CMsm(2.0 * b + 1);
    return (2.0 * b + 1) + 2.0 * b * ADD_OVER_HECM; // Base
}
static double Indiv() { return (UsesMsm() || C.variant == "ind") ? C_IND_MSM : C_IND_BASE; }

static double
BisectCost(const std::vector<uint8_t>& valid, size_t l, size_t r, uint64_t& tests)
{
    size_t m = r - l;
    if (m == 0)
        return 0;
    if (m == 1)
    {
        tests++;
        return Indiv();
    }
    tests++;
    double c = BatchTest(m);
    bool allOk = true;
    for (size_t i = l; i < r; ++i)
        allOk &= valid[i];
    if (allOk)
        return c;
    size_t mid = l + m / 2;
    return c + BisectCost(valid, l, mid, tests) + BisectCost(valid, mid, r, tests);
}
static double
DorfmanCost(const std::vector<uint8_t>& valid, uint32_t g, uint64_t& tests)
{
    size_t b = valid.size();
    tests++;
    double c = BatchTest(b);
    bool allOk = std::all_of(valid.begin(), valid.end(), [](uint8_t v) { return v; });
    if (allOk || b == 1)
        return b == 1 ? Indiv() : c;
    if (g <= 1)
    {
        tests += b;
        return c + b * Indiv();
    }
    for (uint32_t j = 0; j < g; ++j)
    {
        std::vector<uint8_t> grp;
        for (size_t i = j; i < b; i += g)
            grp.push_back(valid[i]);
        if (grp.empty())
            continue;
        tests++;
        c += BatchTest(grp.size());
        if (!std::all_of(grp.begin(), grp.end(), [](uint8_t v) { return v; }))
        {
            tests += grp.size();
            c += grp.size() * Indiv();
        }
    }
    return c;
}
// MSM-aware adaptive batch controller (expected-cost minimisation, closed form)
struct Controller
{
    double mu = 0.0, lam = 0.2;
    double Expected(uint32_t b, uint32_t g) const
    {
        double pf = 1 - std::pow(1 - mu, b);
        if (b == 1)
            return Indiv();
        double c = BatchTest(b);
        if (g <= 1)
            return c + pf * b * Indiv();
        double sz = double(b) / g, pg = 1 - std::pow(1 - mu, sz);
        return c + pf * g * BatchTest(std::max<uint32_t>(1, (uint32_t)std::round(sz))) + g * pg * sz * Indiv();
    }
    double Worst(uint32_t b, uint32_t g) const
    {
        return BatchTest(b) + (g > 1 ? g * BatchTest(std::max<uint32_t>(1, b / g)) : 0) + b * Indiv();
    }
    // returns (b*, g*) minimising expected cost per report under a worst-case time budget
    std::pair<uint32_t, uint32_t> Decide(double budgetHecm) const
    {
        uint32_t bb = 1, gb = 1;
        double best = Indiv();
        for (uint32_t b : {2u, 4u, 8u, 16u, 32u, 64u, 128u, 256u})
            for (uint32_t g : {1u, 2u, 4u, 8u, 16u})
            {
                if (g > b || Worst(b, g) > budgetHecm)
                    continue;
                double c = Expected(b, g) / b;
                if (c < best - 1e-12)
                {
                    best = c;
                    bb = b;
                    gb = g;
                }
            }
        return {bb, gb};
    }
    void Update(uint32_t n, uint32_t bad)
    {
        if (n)
            mu = (1 - lam) * mu + lam * double(bad) / n;
    }
};

// --------------------------------------------------------------------------- message sizes (B)
// HiBaF v2 report: ID4 w4 t4 tau1 nu12 C8 T16 U64 s32 MAC8 = 153
static uint32_t ReportSize() { return C.variant == "sym" ? 49 : 153; }
static uint32_t RecordSize() { return C.variant == "sym" ? 49 : 145; } // report without link MAC
static const uint32_t SIG = 96, BEACON_COL = 230;
static uint32_t BeaconSensorSize() { return C.variant == "sym" ? 72 : 230; }

// ------------------------------------------------------------------------------- wire formats
#pragma pack(push, 1)
struct Rec
{
    uint32_t sensor, seq, window;
    int64_t genNs;
    uint8_t valid, attacker;
    uint16_t col;
};
#pragma pack(pop)
enum MsgType : uint8_t
{
    M_REPORT = 1,
    M_BEACON_COL = 2,
    M_BEACON_S = 3,
    M_CONTAINER = 4,
    M_NOTICE = 5,
    M_RLPUSH = 6,
    M_SITE = 7,
    M_EVIDENCE = 8,
    M_CONFIRM = 9
};

static std::vector<uint8_t>
MakeBuf(uint8_t type, const std::vector<uint8_t>& meta, uint32_t total)
{
    std::vector<uint8_t> b(std::max<uint32_t>(total, meta.size() + 1), 0);
    b[0] = type;
    std::memcpy(b.data() + 1, meta.data(), meta.size());
    return b;
}
template <typename T>
static void
Put(std::vector<uint8_t>& v, const T& x)
{
    const uint8_t* p = reinterpret_cast<const uint8_t*>(&x);
    v.insert(v.end(), p, p + sizeof(T));
}
template <typename T>
static T
Get(const uint8_t* p)
{
    T x;
    std::memcpy(&x, p, sizeof(T));
    return x;
}

// TCP framing helper: [u32 len][body]
struct TcpLink
{
    Ptr<Socket> sock;
    std::deque<uint8_t> tx;
    std::string rx;
    std::function<void(const std::string&)> onMsg;
    void Send(const std::vector<uint8_t>& body)
    {
        uint32_t len = body.size();
        const uint8_t* lp = reinterpret_cast<const uint8_t*>(&len);
        tx.insert(tx.end(), lp, lp + 4);
        tx.insert(tx.end(), body.begin(), body.end());
        Pump();
    }
    void Pump()
    {
        if (!sock)
            return;
        while (!tx.empty())
        {
            uint32_t avail = sock->GetTxAvailable();
            if (avail == 0)
                return;
            uint32_t n = std::min<uint32_t>(avail, std::min<size_t>(tx.size(), 16000));
            std::vector<uint8_t> chunk(tx.begin(), tx.begin() + n);
            int sent = sock->Send(chunk.data(), n, 0);
            if (sent <= 0)
                return;
            tx.erase(tx.begin(), tx.begin() + sent);
        }
    }
    void OnSendable(Ptr<Socket>, uint32_t) { Pump(); }
    void OnRecv(Ptr<Socket> s)
    {
        Ptr<Packet> p;
        while ((p = s->Recv()))
        {
            std::string d(p->GetSize(), '\0');
            p->CopyData(reinterpret_cast<uint8_t*>(d.data()), d.size());
            rx += d;
            while (rx.size() >= 4)
            {
                uint32_t len;
                std::memcpy(&len, rx.data(), 4);
                if (rx.size() < 4 + len)
                    break;
                std::string body = rx.substr(4, len);
                rx.erase(0, 4 + len);
                if (onMsg)
                    onMsg(body);
            }
        }
    }
    void Attach(Ptr<Socket> s)
    {
        sock = s;
        s->SetRecvCallback(MakeCallback(&TcpLink::OnRecv, this));
        s->SetSendCallback(MakeCallback(&TcpLink::OnSendable, this));
    }
};

// ---------------------------------------------------------------------------------- CPU model
struct Cpu
{
    double busyUntil = 0, busyTotal = 0;
    // returns completion time (s) of a job of `ms` milliseconds submitted now
    double Run(double ms)
    {
        double now = Simulator::Now().GetSeconds();
        double start = std::max(now, busyUntil);
        busyUntil = start + ms / 1000.0;
        if (start >= C.warmup)
            busyTotal += ms / 1000.0;
        return busyUntil;
    }
};

// ------------------------------------------------------------------------------- global stats
struct Stats
{
    uint64_t generated = 0, noBeacon = 0, sent = 0, committed = 0, committedLate = 0, attackCommitted = 0;
    uint64_t macDrop = 0, windowDrop = 0, replayDrop = 0, quotaDrop = 0, negDrop = 0, revokedDrop = 0, sigDrop = 0;
    uint64_t invalidVerified = 0, verifiedOk = 0, batchTests = 0, batches = 0, batchSizeSum = 0;
    double groupHecmCol = 0;
    std::vector<double> e2e, auth;
    std::map<uint32_t, std::vector<double>> perSensorDelay;
    uint64_t sensorTxBytes = 0, sensorTxFrames = 0, sensorRxFrames = 0, sensorRxBytes = 0;
    uint64_t macTxDrop = 0, beaconsSentToSensors = 0;
    uint64_t lanBytes = 0, wanBytes = 0;
    double sensorCpuMs = 0;
    double firstInvalid = -1, firstNotice = -1, revIssue = -1;
    std::map<uint32_t, double> revInstall; // collector -> time
    uint64_t falseRevoked = 0, noticesRejected = 0, noticesReceived = 0;
    uint64_t rlBytes = 0;
    double beHecm = 0, stHecm = 0;
    uint64_t sensorWindows = 0, sensorWindowsMissed = 0;
} S;
static std::set<std::pair<uint32_t, uint32_t>> g_committedKeys;
static std::ofstream g_perRep;

// ------------------------------------------------------------------------------------ entities
struct Collector;
struct Station;
struct BackEnd;
static std::vector<Collector*> g_cols;
static Station* g_st = nullptr;
static BackEnd* g_be = nullptr;

struct Sensor
{
    uint32_t id, pond;
    bool attacker = false;
    Ptr<Node> node;
    Ptr<Socket> tx, rxBeacon;
    Ipv6Address colAddr;
    Cpu cpu;
    int64_t curWindow = -1;
    uint32_t seq = 0;
    Ptr<UniformRandomVariable> rv;
    double Interval(double t) const
    {
        if (C.burstStart >= 0 && t >= C.burstStart && t < C.burstStart + C.burstDur)
            return C.burstInterval;
        return C.reportInterval;
    }
    void Start(double t0)
    {
        Simulator::Schedule(Seconds(t0), &Sensor::Generate, this);
        if (attacker)
            Simulator::Schedule(Seconds(C.attackStart + rv->GetValue(0, 1.0 / C.attackRate)), &Sensor::Attack, this);
    }
    void Generate()
    {
        double now = Simulator::Now().GetSeconds();
        if (now > C.simTime - C.drain)
            return;
        if (!attacker)
        {
            bool count = now >= C.warmup;
            if (count)
                S.generated++;
            if (curWindow < 0)
            {
                if (count)
                    S.noBeacon++;
            }
            else
            {
                double ms = C.tHecmSensor + C.tAeadSensor + 3 * C.tHashSensor; // sign + AEAD + KDF/H2/MAC
                double done = cpu.Run(ms);
                if (now >= C.warmup)
                    S.sensorCpuMs += ms;
                Rec r{id, seq++, (uint32_t)curWindow, Simulator::Now().GetNanoSeconds(), 1, 0, 0};
                Simulator::Schedule(Seconds(done - now), &Sensor::SendRec, this, r);
            }
        }
        double iv = Interval(now);
        Simulator::Schedule(Seconds(iv * rv->GetValue(0.95, 1.05)), &Sensor::Generate, this);
    }
    void Attack()
    {
        double now = Simulator::Now().GetSeconds();
        if (now > C.simTime - C.drain)
            return;
        if (curWindow >= 0)
        {
            Rec r{id, 1000000 + seq++, (uint32_t)curWindow, Simulator::Now().GetNanoSeconds(), 0, 1, 0};
            SendRec(r); // invalid signature, valid link MAC (insider)
        }
        Simulator::Schedule(Seconds(rv->GetValue(0.5, 1.5) / C.attackRate), &Sensor::Attack, this);
    }
    void SendRec(Rec r)
    {
        std::vector<uint8_t> meta;
        Put(meta, r);
        meta.push_back(1); // link MAC valid
        auto b = MakeBuf(M_REPORT, meta, ReportSize());
        tx->SendTo(Create<Packet>(b.data(), b.size()), 0, Inet6SocketAddress(colAddr, 9000));
        if (!r.attacker && Simulator::Now().GetSeconds() >= C.warmup)
            S.sent++;
    }
    void OnBeacon(Ptr<Socket> s)
    {
        Ptr<Packet> p;
        while ((p = s->Recv()))
        {
            std::vector<uint8_t> d(p->GetSize());
            p->CopyData(d.data(), d.size());
            if (d[0] != M_BEACON_S)
                continue;
            uint32_t w = Get<uint32_t>(d.data() + 1);
            if ((int64_t)w <= curWindow)
                continue; // repeat or old (monotonic rule)
            // verify station signature + TTP RL signature: 2 x (2-term MSM | 2 HECM | sym MAC)
            double ms = C.variant == "sym" ? 0.05 : 2 * Indiv() * C.tHecmSensor;
            double done = cpu.Run(ms);
            if (Simulator::Now().GetSeconds() >= C.warmup)
                S.sensorCpuMs += ms;
            Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), &Sensor::Install, this, w);
        }
    }
    void Install(uint32_t w)
    {
        if ((int64_t)w > curWindow)
            curWindow = w;
    }
};
static std::vector<Sensor*> g_sensors;

struct Pending
{
    Rec r;
    double arrive;
};

struct Collector
{
    uint32_t id;
    Ptr<Node> node;
    Ptr<Socket> udp, bcast;
    Ptr<NetDevice> sixDev;
    TcpLink up;   // -> station
    TcpLink down; // <- station (beacons, RL)
    Cpu cpu;
    Controller ctrl;
    int64_t curWindow = -1;
    double windowStart = 0;
    std::set<std::pair<uint32_t, uint32_t>> accepted;
    std::set<uint32_t> neg, revoked;
    std::map<uint32_t, uint32_t> count;
    std::deque<Pending> q;
    bool flushScheduled = false;
    bool verifying = false;
    uint32_t Quota() const
    {
        double t = C.quotaMinInterval > 0 ? C.quotaMinInterval : C.reportInterval;
        return (uint32_t)std::ceil(C.window / t) + 2;
    }

    void OnReport(Ptr<Socket> s)
    {
        Ptr<Packet> p;
        Address from;
        while ((p = s->RecvFrom(from)))
        {
            std::vector<uint8_t> d(p->GetSize());
            p->CopyData(d.data(), d.size());
            if (d[0] != M_REPORT)
                continue;
            Rec r = Get<Rec>(d.data() + 1);
            uint8_t macOk = d[1 + sizeof(Rec)];
            bool count_ = Simulator::Now().GetSeconds() >= C.warmup;
            cpu.Run(C.tHashCol); // link-MAC check
            if (!macOk)
            {
                if (count_)
                    S.macDrop++;
                continue;
            }
            Admit(r, count_);
        }
    }
    void Admit(Rec r, bool cnt)
    {
        double now = Simulator::Now().GetSeconds();
        bool winOk = (int64_t)r.window == curWindow ||
                     ((int64_t)r.window == curWindow - 1 && now < windowStart + C.grace);
        if (!winOk)
        {
            if (cnt && !r.attacker)
                S.windowDrop++;
            return;
        }
        if (revoked.count(r.sensor))
        {
            if (cnt)
                S.revokedDrop++;
            return;
        }
        if (C.defenses && neg.count(r.sensor))
        {
            if (cnt)
                S.negDrop++;
            return;
        }
        auto key = std::make_pair(r.sensor, r.seq);
        if (accepted.count(key))
        {
            if (cnt)
                S.replayDrop++;
            return;
        }
        if (C.defenses && ++count[r.sensor] > Quota())
        {
            if (cnt)
                S.quotaDrop++;
            return;
        }
        r.col = id;
        if (C.variant == "sym")
        { // per-hop AEAD decrypt + re-protect toward station: cheap, no batching
            double done = cpu.Run(4 * C.tHashCol);
            Simulator::Schedule(Seconds(done - now), &Collector::Stage, this, Pending{r, now});
            return;
        }
        if (C.variant == "ind")
        {
            double done = cpu.Run(C_IND_MSM * C.tHecmCol + 2 * C.tHashCol);
            std::vector<Pending> one{{r, now}};
            if (cnt)
            {
                S.batchTests++;
                S.groupHecmCol += C_IND_MSM;
            }
            Simulator::Schedule(Seconds(done - now), &Collector::Verified, this, one, std::vector<uint8_t>{r.valid});
            return;
        }
        q.push_back({r, now});
        MaybeFlush();
    }
    uint32_t Threshold()
    {
        if (C.variant == "msm")
            return ctrl.Decide(C.budgetTime * 1000.0 / C.tHecmCol).first;
        return 512; // fixed policies flush on timer
    }
    void MaybeFlush()
    {
        if (q.empty() || verifying)
            return;
        uint32_t b = Threshold();
        double now = Simulator::Now().GetSeconds();
        if (q.size() >= b || now - q.front().arrive >= C.maxWait - 1e-9)
        {
            Flush();
            return;
        }
        if (!flushScheduled)
        {
            flushScheduled = true;
            Simulator::Schedule(Seconds(q.front().arrive + C.maxWait - now), &Collector::TimerFlush, this);
        }
    }
    void TimerFlush()
    {
        flushScheduled = false;
        MaybeFlush();
    }
    void Flush()
    {
        double now = Simulator::Now().GetSeconds();
        uint32_t b = 512, g = 1;
        if (C.variant == "msm")
        {
            auto d = ctrl.Decide(C.budgetTime * 1000.0 / C.tHecmCol);
            b = d.first;
            g = d.second;
        }
        uint32_t take = std::min<uint32_t>(q.size(), C.variant == "msm" ? std::max<uint32_t>(b, 1) : 512);
        if (C.variant == "msm" && take < b)
        {
            const double budget =
                C.budgetTime * 1000.0 / C.tHecmCol;

            double best = 1e18;
            bool found = false;

            for (uint32_t gg : {1u, 2u, 4u, 8u, 16u})
            {
                if (gg > take || take % gg != 0)
                    continue;

                if (take > 1 && ctrl.Worst(take, gg) > budget)
                    continue;

                double cost = ctrl.Expected(take, gg);

                if (cost < best)
                {
                    best = cost;
                    g = gg;
                    found = true;
                }
            }

            if (!found)
            {
                // Fall back to one individual verification
                take = 1;
                g = 1;
            }
        }
        std::vector<Pending> batch(q.begin(), q.begin() + take);
        q.erase(q.begin(), q.begin() + take);
        std::vector<uint8_t> valid;
        for (auto& x : batch)
            valid.push_back(x.r.valid);
        uint64_t tests = 0;
        double hecm = C.variant == "msm" ? DorfmanCost(valid, g, tests) : BisectCost(valid, 0, valid.size(), tests);
        double ms = hecm * C.tHecmCol + batch.size() * C.tHashCol; // + H2 per report
        verifying = true;
        double done = cpu.Run(ms);
        if (now >= C.warmup)
        {
            S.batchTests += tests;
            S.batches++;
            S.batchSizeSum += batch.size();
            S.groupHecmCol += hecm;
        }
        uint32_t bad = std::count(valid.begin(), valid.end(), 0);
        ctrl.Update(valid.size(), bad);
        Simulator::Schedule(Seconds(done - now), &Collector::Verified, this, batch, valid);
    }
    void Verified(std::vector<Pending> batch, std::vector<uint8_t> valid)
    {
        verifying = false;
        double now = Simulator::Now().GetSeconds();
        std::vector<Pending> ok;
        for (size_t i = 0; i < batch.size(); ++i)
        {
            bool cnt = batch[i].arrive >= C.warmup;
            if (!valid[i])
            {
                if (cnt)
                    S.sigDrop++;
                if (S.firstInvalid < 0 && batch[i].r.attacker)
                    S.firstInvalid = batch[i].arrive;
                if (C.defenses && !neg.count(batch[i].r.sensor))
                {
                    neg.insert(batch[i].r.sensor);
                    Notice(batch[i].r.sensor);
                }
                continue;
            }
            auto key = std::make_pair(batch[i].r.sensor, batch[i].r.seq);
            if (accepted.count(key))
                continue;
            accepted.insert(key);
            if (cnt)
            {
                S.verifiedOk++;
                S.auth.push_back(now - batch[i].arrive);
            }
            ok.push_back(batch[i]);
        }
        if (C.variant == "ind")
        {
            for (auto& x : ok)
            {
                if (x.arrive >= C.warmup)
                {
                    S.verifiedOk--; // counted again in Stage
                    S.auth.pop_back();
                }
                Stage(x);
            }
            return;
        }
        if (!ok.empty())
        {
            double done = cpu.Run(C.tHecmCol + 2 * C.tHashCol); // container signature
            Simulator::Schedule(Seconds(done - now), &Collector::Ship, this, ok, now);
        }
        MaybeFlush();
    }
    std::vector<Pending> staged;
    bool stageTimer = false;
    void Stage(Pending x)
    {
        if (x.arrive >= C.warmup)
        {
            S.verifiedOk++;
            S.auth.push_back(Simulator::Now().GetSeconds() - x.arrive);
        }
        staged.push_back(x);
        if (!stageTimer)
        {
            stageTimer = true;
            Simulator::Schedule(Seconds(C.maxWait), &Collector::ShipStaged, this);
        }
    }
    void ShipStaged()
    {
        stageTimer = false;
        if (staged.empty())
            return;
        auto ok = staged;
        staged.clear();
        double now = Simulator::Now().GetSeconds();
        double done = cpu.Run((C.variant == "sym" ? 0.01 : C.tHecmCol) + 2 * C.tHashCol); // container protection
        Simulator::Schedule(Seconds(done - now), &Collector::Ship, this, ok, now);
    }
    void Ship(std::vector<Pending> ok, double)
    {
        std::vector<uint8_t> meta;
        Put(meta, (uint16_t)id);
        Put(meta, (uint32_t)ok.size());
        for (auto& x : ok)
            Put(meta, x.r);
        uint32_t total = 16 + ok.size() * RecordSize() + (C.variant == "sym" ? 16 : SIG);
        auto b = MakeBuf(M_CONTAINER, meta, total);
        if (Simulator::Now().GetSeconds() >= C.warmup)
            S.lanBytes += b.size() + 4;
        up.Send(b);
    }
    void Notice(uint32_t sensor)
    {
        if (S.firstNotice < 0)
            S.firstNotice = Simulator::Now().GetSeconds();
        std::vector<uint8_t> meta;
        Put(meta, sensor);
        double done = cpu.Run(C.tHecmCol); // sign the notice
        auto b = MakeBuf(M_NOTICE, meta, 32 + SIG + (C.evidence ? 153 : 0));
        Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), [this, b]() { up.Send(b); });
    }
    void OnDown(const std::string& body)
    {
        const uint8_t* d = reinterpret_cast<const uint8_t*>(body.data());
        if (d[0] == M_BEACON_COL)
        {
            uint32_t w = Get<uint32_t>(d + 1);
            double ms = C.variant == "sym" ? 0.01 : 2 * Indiv() * C.tHecmCol; // beacon + RL signatures
            double done = cpu.Run(ms);
            Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), &Collector::InstallWindow, this, w);
        }
        else if (d[0] == M_RLPUSH)
        {
            uint32_t sensor = Get<uint32_t>(d + 1 + 4);
            double done = cpu.Run(Indiv() * C.tHecmCol);
            Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), [this, sensor]() {
                revoked.insert(sensor);
                if (!S.revInstall.count(id))
                    S.revInstall[id] = Simulator::Now().GetSeconds();
            });
        }
    }
    void InstallWindow(uint32_t w)
    {
        if ((int64_t)w <= curWindow)
            return;
        curWindow = w;
        windowStart = Simulator::Now().GetSeconds();
        count.clear();
        neg.clear();
        // accepted cache keyed by (sensor, seq) persists for the previous window's grace period
        for (uint32_t k = 0; k < C.beaconRepeats; ++k)
            Simulator::Schedule(Seconds(k * C.beaconSpacing + id * C.beaconStagger), &Collector::Broadcast, this, w);
    }
    void Broadcast(uint32_t w)
    {
        std::vector<uint8_t> meta;
        Put(meta, w);
        auto b = MakeBuf(M_BEACON_S, meta, BeaconSensorSize());
        bcast->SendTo(Create<Packet>(b.data(), b.size()), 0,
                      Inet6SocketAddress(Ipv6Address::GetAllNodesMulticast(), 9001));
        if (Simulator::Now().GetSeconds() >= C.warmup)
            S.beaconsSentToSensors++;
    }
};

struct Station
{
    Ptr<Node> node;
    std::vector<TcpLink*> fromCol, toCol;
    TcpLink toBe;
    Cpu cpu;
    uint32_t window = 0, rlVersion = 0;
    std::vector<std::vector<Rec>> pendingConts;
    std::set<uint32_t> revoked;
    void Beacon()
    {
        window++;
        double done = cpu.Run(C.tHecmSt + 2 * C.tHashCol);
        Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), [this]() {
            std::vector<uint8_t> meta;
            Put(meta, window);
            auto b = MakeBuf(M_BEACON_COL, meta, BEACON_COL);
            for (auto* l : toCol)
            {
                l->Send(b);
                if (Simulator::Now().GetSeconds() >= C.warmup)
                    S.lanBytes += b.size() + 4;
            }
        });
        Simulator::Schedule(Seconds(C.window), &Station::Beacon, this);
    }
    void OnUp(const std::string& body)
    {
        const uint8_t* d = reinterpret_cast<const uint8_t*>(body.data());
        if (d[0] == M_CONTAINER)
        {
            uint32_t n = Get<uint32_t>(d + 1 + 2);
            std::vector<Rec> recs;
            for (uint32_t i = 0; i < n; ++i)
                recs.push_back(Get<Rec>(d + 1 + 6 + i * sizeof(Rec)));
            pendingConts.push_back(recs);
        }
        else if (d[0] == M_NOTICE)
        {
            uint32_t sensor = Get<uint32_t>(d + 1);
            if (!C.defenses || revoked.count(sensor) || pendingEvidence.count(sensor))
                return;
            S.noticesReceived++;
            if (C.evidence)
            {
                // verify the collector's notice signature, then forward the report to the back end,
                // which alone can check the sensor's GCM tag
                pendingEvidence.insert(sensor);
                double done = cpu.Run(Indiv() * C.tHecmSt);
                Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), [this, sensor]() {
                    std::vector<uint8_t> meta;
                    Put(meta, sensor);
                    toBe.Send(MakeBuf(M_EVIDENCE, meta, 16 + 153));
                });
                return;
            }
            Revoke(sensor);
        }
        else if (d[0] == M_CONFIRM)
        {
            uint32_t sensor = Get<uint32_t>(d + 1);
            uint8_t ok = d[1 + 4];
            pendingEvidence.erase(sensor);
            if (!ok)
            {
                S.noticesRejected++;
                return;
            }
            Revoke(sensor);
        }
    }
    std::set<uint32_t> pendingEvidence;
    void Revoke(uint32_t sensor)
    {
        {
            if (revoked.count(sensor))
                return;
            revoked.insert(sensor);
            if (!g_sensors[sensor]->attacker)
                S.falseRevoked++;
            // (notice signature check if no evidence step) + TTP decision (100 ms policy delay) + RL signature
            double done = cpu.Run((C.evidence ? 0.0 : Indiv() * C.tHecmSt) + C.tHecmSt) + 0.100;
            Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), [this, sensor]() {
                rlVersion++;
                if (S.revIssue < 0)
                    S.revIssue = Simulator::Now().GetSeconds();
                std::vector<uint8_t> meta;
                Put(meta, rlVersion);
                Put(meta, sensor);
                auto b = MakeBuf(M_RLPUSH, meta, 16 + 4 + SIG);
                for (auto* l : toCol)
                {
                    l->Send(b);
                    S.rlBytes += b.size() + 4;
                }
            });
        }
    }
    void Flush()
    {
        Simulator::Schedule(Seconds(C.stationFlush), &Station::Flush, this);
        if (pendingConts.empty())
            return;
        auto conts = pendingConts;
        pendingConts.clear();
        uint32_t m = conts.size();
        double hecm = C.variant == "sym" ? 0 : (m == 1 ? Indiv() : (C.variant == "ind" ? m * C_IND_MSM : BatchTest(m)));
        size_t nrec = 0;
        for (auto& c : conts)
            nrec += c.size();
        double ms = hecm * C.tHecmSt + (C.variant == "sym" ? (4 * nrec) * C.tHashCol : 0) + C.tHecmSt;
        if (Simulator::Now().GetSeconds() >= C.warmup)
            S.stHecm += hecm + 1;
        double done = cpu.Run(ms);
        Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), [this, conts, nrec]() {
            std::vector<uint8_t> meta;
            Put(meta, (uint32_t)nrec);
            for (auto& c : conts)
                for (auto& r : c)
                    Put(meta, r);
            uint32_t total = 16 + nrec * (RecordSize() + 2) + conts.size() * (SIG + 16) + SIG;
            auto b = MakeBuf(M_SITE, meta, total);
            if (Simulator::Now().GetSeconds() >= C.warmup)
                S.wanBytes += b.size() + 4;
            toBe.Send(b);
        });
    }
};

struct BackEnd
{
    Ptr<Node> node;
    TcpLink fromSt;
    Cpu cpu;
    Ptr<UniformRandomVariable> rv;
    void OnSite(const std::string& body)
    {
        const uint8_t* d = reinterpret_cast<const uint8_t*>(body.data());
        if (d[0] == M_EVIDENCE)
        {
            // derive the window key, check the GCM tag (valid only if produced with the sensor's
            // ratchet state) and confirm the signature is invalid
            uint32_t sensor = Get<uint32_t>(d + 1);
            double done = cpu.Run(C.tAeadBe + 0.001 + Indiv() * C.tHecmBe);
            Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), [this, sensor]() {
                std::vector<uint8_t> meta;
                Put(meta, sensor);
                Put(meta, (uint8_t)(g_sensors[sensor]->attacker ? 1 : 0));
                fromSt.Send(MakeBuf(M_CONFIRM, meta, 16 + SIG));
            });
            return;
        }
        if (d[0] != M_SITE)
            return;
        uint32_t n = Get<uint32_t>(d + 1);
        std::vector<Rec> recs;
        for (uint32_t i = 0; i < n; ++i)
            recs.push_back(Get<Rec>(d + 1 + 4 + i * sizeof(Rec)));
        // station signature + per report KDF/AEAD + theta audit
        double theta = C.variant == "ind" ? 1.0 : (C.variant == "sym" ? 0.0 : C.theta);
        uint32_t a = 0;
        for (uint32_t i = 0; i < n; ++i)
            a += rv->GetValue() < theta;
        double hecm = C.variant == "sym" ? 0 : Indiv();
        if (a > 0)
            hecm += C.variant == "ind" ? a * C_IND_MSM : (a == 1 ? Indiv() : BatchTest(a));
        double ms = hecm * C.tHecmBe + n * (C.tAeadBe + 0.001);
        if (Simulator::Now().GetSeconds() >= C.warmup)
            S.beHecm += hecm;
        double done = cpu.Run(ms);
        Simulator::Schedule(Seconds(done - Simulator::Now().GetSeconds()), &BackEnd::Commit, this, recs);
    }
    void Commit(std::vector<Rec> recs)
    {
        double now = Simulator::Now().GetSeconds();
        for (auto& r : recs)
        {
            double gen = r.genNs * 1e-9;
            if (r.attacker)
            {
                S.attackCommitted++;
                continue;
            }
            auto key = std::make_pair(r.sensor, r.seq);
            if (g_committedKeys.count(key))
                continue; // BE in-loop dedupe
            g_committedKeys.insert(key);
            if (gen < C.warmup)
                continue;
            S.committed++;
            double dl = now - gen;
            S.e2e.push_back(dl);
            S.perSensorDelay[r.sensor].push_back(dl);
            if (dl > C.deadline)
                S.committedLate++;
            if (g_perRep.is_open())
                g_perRep << r.sensor << "," << gen << "," << dl << "\n";
        }
    }
};

// ------------------------------------------------------------------------------------- traces
static std::set<uint32_t> g_sensorNodeIds;
static void
PhyTx(uint32_t nodeId, Ptr<const Packet> p)
{
    if (Simulator::Now().GetSeconds() < C.warmup || !g_sensorNodeIds.count(nodeId))
        return;
    S.sensorTxFrames++;
    S.sensorTxBytes += p->GetSize() + 6; // + SHR(5) + PHR(1)
}
static void
MacRxS(uint32_t nodeId, Ptr<const Packet> p)
{
    if (Simulator::Now().GetSeconds() < C.warmup || !g_sensorNodeIds.count(nodeId))
        return;
    S.sensorRxFrames++;
    S.sensorRxBytes += p->GetSize() + 11 + 6; // MSDU + MHR/FCS + SHR/PHR
}
static void
MacTxOkS(uint32_t nodeId, Ptr<const Packet>)
{
    if (Simulator::Now().GetSeconds() < C.warmup || !g_sensorNodeIds.count(nodeId))
        return;
    S.sensorRxBytes += 11; // received ACK frame (5 B MPDU + 6 B SHR/PHR)
}
[[maybe_unused]] static void
PhyRx(uint32_t nodeId, Ptr<const Packet> p, double)
{
    if (Simulator::Now().GetSeconds() < C.warmup || !g_sensorNodeIds.count(nodeId))
        return;
    S.sensorRxFrames++;
    S.sensorRxBytes += p->GetSize() + 6;
}
static void
MacDrop(Ptr<const Packet>)
{
    if (Simulator::Now().GetSeconds() >= C.warmup)
        S.macTxDrop++;
}

static double
Pct(std::vector<double> v, double q)
{
    if (v.empty())
        return NAN;
    std::sort(v.begin(), v.end());
    size_t i = std::min(v.size() - 1, (size_t)std::floor(q * (v.size() - 1) + 0.5));
    return v[i];
}

int
main(int argc, char* argv[])
{
    CommandLine cmd(__FILE__);
    cmd.AddValue("variant", "msm|msmfix|base|ind|sym", C.variant);
    cmd.AddValue("nSensors", "total sensors", C.nSensors);
    cmd.AddValue("perPond", "sensors per pond/collector", C.perPond);
    cmd.AddValue("reportInterval", "s", C.reportInterval);
    cmd.AddValue("window", "reporting window s", C.window);
    cmd.AddValue("simTime", "s", C.simTime);
    cmd.AddValue("warmup", "s", C.warmup);
    cmd.AddValue("drain", "s without new reports at the end", C.drain);
    cmd.AddValue("theta", "BE audit rate", C.theta);
    cmd.AddValue("radius", "sensor placement radius m", C.radius);
    cmd.AddValue("deadline", "DT freshness deadline s", C.deadline);
    cmd.AddValue("beaconRepeats", "beacon rebroadcasts", C.beaconRepeats);
    cmd.AddValue("wanRate", "WAN rate", C.wanRate);
    cmd.AddValue("wanDelayMs", "WAN one-way delay ms", C.wanDelayMs);
    cmd.AddValue("wanLoss", "WAN packet error rate", C.wanLoss);
    cmd.AddValue("wanOutageStart", "s (<0 none)", C.wanOutageStart);
    cmd.AddValue("wanOutageDur", "s", C.wanOutageDur);
    cmd.AddValue("maxWait", "collector max batching wait s", C.maxWait);
    cmd.AddValue("stationFlush", "station flush period s", C.stationFlush);
    cmd.AddValue("budgetTime", "controller worst-case time budget s", C.budgetTime);
    cmd.AddValue("quotaMinInterval", "fastest legitimate report interval used to size the quota (s)", C.quotaMinInterval);
    cmd.AddValue("attackers", "compromised insider sensors", C.attackers);
    cmd.AddValue("attackRate", "invalid reports/s per attacker", C.attackRate);
    cmd.AddValue("attackStart", "s", C.attackStart);
    cmd.AddValue("defenses", "neg cache + quota + revocation", C.defenses);
    cmd.AddValue("evidence", "revocation requires BE-validated evidence", C.evidence);
    cmd.AddValue("byzNoticeRate", "false accusations/s from Byzantine collector 0", C.byzNoticeRate);
    cmd.AddValue("sharedChannel", "all ponds share one 802.15.4 channel", C.sharedChannel);
    cmd.AddValue("beaconStagger", "per-collector beacon rebroadcast offset s", C.beaconStagger);
    cmd.AddValue("pondSpacing", "m between pond centres (shared channel)", C.pondSpacing);
    cmd.AddValue("outsiderRate", "forged frames/s per pond (bad MAC)", C.outsiderRate);
    cmd.AddValue("burstStart", "s (<0 none)", C.burstStart);
    cmd.AddValue("burstDur", "s", C.burstDur);
    cmd.AddValue("burstInterval", "s", C.burstInterval);
    cmd.AddValue("tHecmSensor", "ms", C.tHecmSensor);
    cmd.AddValue("tHecmCol", "ms", C.tHecmCol);
    cmd.AddValue("tHecmSt", "ms", C.tHecmSt);
    cmd.AddValue("tHecmBe", "ms", C.tHecmBe);
    cmd.AddValue("run", "RNG run", C.run);
    cmd.AddValue("out", "output dir", C.out);
    cmd.AddValue("tag", "scenario tag", C.tag);
    cmd.AddValue("perReport", "write per-report delays", C.perReport);
    cmd.Parse(argc, argv);

    RngSeedManager::SetSeed(20261015);
    RngSeedManager::SetRun(C.run);
    Config::SetDefault("ns3::TcpSocket::SndBufSize", UintegerValue(1 << 21));
    Config::SetDefault("ns3::TcpSocket::RcvBufSize", UintegerValue(1 << 21));
    Config::SetDefault("ns3::TcpSocket::SegmentSize", UintegerValue(1400));

    uint32_t P = std::max<uint32_t>(1, (C.nSensors + C.perPond - 1) / C.perPond);
    NodeContainer colNodes, stNode, beNode;
    colNodes.Create(P);
    stNode.Create(1);
    beNode.Create(1);
    InternetStackHelper inet;
    inet.Install(colNodes);
    inet.Install(stNode);
    inet.Install(beNode);

    // ---------------- backhaul
    CsmaHelper csma;
    csma.SetChannelAttribute("DataRate", StringValue("100Mbps"));
    csma.SetChannelAttribute("Delay", TimeValue(MicroSeconds(5)));
    NodeContainer lan(colNodes);
    lan.Add(stNode);
    NetDeviceContainer lanDev = csma.Install(lan);
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue(C.wanRate));
    p2p.SetChannelAttribute("Delay", TimeValue(MilliSeconds(C.wanDelayMs)));
    NetDeviceContainer wanDev = p2p.Install(stNode.Get(0), beNode.Get(0));
    Ptr<RateErrorModel> wanErr = CreateObject<RateErrorModel>();
    wanErr->SetAttribute("ErrorUnit", StringValue("ERROR_UNIT_PACKET"));
    wanErr->SetAttribute("ErrorRate", DoubleValue(C.wanLoss));
    wanErr->AssignStreams(C.run * 7 + 3);
    wanDev.Get(1)->SetAttribute("ReceiveErrorModel", PointerValue(wanErr));
    Ptr<RateErrorModel> wanErrUp = CreateObject<RateErrorModel>();
    wanErrUp->SetAttribute("ErrorUnit", StringValue("ERROR_UNIT_PACKET"));
    wanErrUp->SetAttribute("ErrorRate", DoubleValue(C.wanLoss));
    wanDev.Get(0)->SetAttribute("ReceiveErrorModel", PointerValue(wanErrUp));
    if (C.wanOutageStart >= 0)
    {
        Simulator::Schedule(Seconds(C.wanOutageStart), [=]() {
            wanErr->SetAttribute("ErrorRate", DoubleValue(1.0));
            wanErrUp->SetAttribute("ErrorRate", DoubleValue(1.0));
        });
        Simulator::Schedule(Seconds(C.wanOutageStart + C.wanOutageDur), [=]() {
            wanErr->SetAttribute("ErrorRate", DoubleValue(C.wanLoss));
            wanErrUp->SetAttribute("ErrorRate", DoubleValue(C.wanLoss));
        });
    }
    Ipv4AddressHelper v4;
    v4.SetBase("10.1.0.0", "255.255.0.0");
    Ipv4InterfaceContainer lanIf = v4.Assign(lanDev);
    v4.SetBase("10.2.0.0", "255.255.255.252");
    Ipv4InterfaceContainer wanIf = v4.Assign(wanDev);
    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    // ---------------- ponds
    Ptr<UniformRandomVariable> urv = CreateObject<UniformRandomVariable>();
    urv->SetStream(C.run * 11 + 1);
    uint32_t sid = 0;
    int64_t stream = 1000;
    for (uint32_t p = 0; p < P; ++p)
    {
        uint32_t n = std::min(C.perPond, C.nSensors - p * C.perPond);
        NodeContainer pond;
        pond.Add(colNodes.Get(p));
        NodeContainer sens;
        sens.Create(n);
        inet.Install(sens);
        pond.Add(sens);
        NodeContainer outsider;
        if (C.outsiderRate > 0)
        {
            outsider.Create(1);
            inet.Install(outsider);
            pond.Add(outsider);
        }
        MobilityHelper mob;
        Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
        uint32_t gridCols = (uint32_t)std::ceil(std::sqrt((double)P));
        double ox = C.sharedChannel ? (p % gridCols) * C.pondSpacing : 0.0;
        double oy = C.sharedChannel ? (p / gridCols) * C.pondSpacing : 0.0;
        pos->Add(Vector(ox, oy, 1.0));
        for (uint32_t i = 1; i < pond.GetN(); ++i)
        {
            double r = C.radius * std::sqrt(urv->GetValue()), a = urv->GetValue(0, 2 * M_PI);
            pos->Add(Vector(ox + r * std::cos(a), oy + r * std::sin(a), 0.3));
        }
        mob.SetPositionAllocator(pos);
        mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
        mob.Install(pond);
        // one helper (and channel) per pond; helpers must outlive the simulation because
        // ~LrWpanHelper disposes its channel
        static std::vector<std::unique_ptr<LrWpanHelper>> helpers;
        bool newHelper = !C.sharedChannel || helpers.empty();
        if (newHelper)
        {
            helpers.emplace_back(std::make_unique<LrWpanHelper>());
            helpers.back()->SetPropagationDelayModel("ns3::ConstantSpeedPropagationDelayModel");
            helpers.back()->AddPropagationLossModel("ns3::LogDistancePropagationLossModel", "Exponent",
                                                    DoubleValue(3.0), "ReferenceLoss", DoubleValue(40.05));
        }
        LrWpanHelper& lr = *helpers.back();
        NetDeviceContainer lrDev = lr.Install(pond);
        stream += lr.AssignStreams(lrDev, stream);
        if (newHelper)
            stream += lr.GetChannel()->AssignStreams(stream);
        lr.CreateAssociatedPan(lrDev, 10 + p);
        SixLowPanHelper six;
        NetDeviceContainer sixDev = six.Install(lrDev);
        stream += six.AssignStreams(sixDev, stream);
        Ipv6AddressHelper v6;
        std::ostringstream pre;
        pre << "2001:" << std::hex << (p + 1) << "::";
        v6.SetBase(Ipv6Address(pre.str().c_str()), Ipv6Prefix(64));
        Ipv6InterfaceContainer ifs = v6.Assign(sixDev);
        for (uint32_t i = 0; i < lrDev.GetN(); ++i)
        {
            auto dev = DynamicCast<lrwpan::LrWpanNetDevice>(lrDev.Get(i));
            uint32_t nid = pond.Get(i)->GetId();
            lr.AddMobility(dev->GetPhy(), pond.Get(i)->GetObject<MobilityModel>());
            lr.AddMobility(dev->GetPhy(), pond.Get(i)->GetObject<MobilityModel>());
            dev->GetPhy()->TraceConnectWithoutContext("PhyTxBegin", MakeBoundCallback(&PhyTx, nid));
            dev->GetMac()->TraceConnectWithoutContext("MacRx", MakeBoundCallback(&MacRxS, nid));
            dev->GetMac()->TraceConnectWithoutContext("MacTxOk", MakeBoundCallback(&MacTxOkS, nid));
            dev->GetMac()->TraceConnectWithoutContext("MacTxDrop", MakeCallback(&MacDrop));
        }

        auto* col = new Collector();
        col->id = p;
        col->node = colNodes.Get(p);
        col->sixDev = sixDev.Get(0);
        col->udp = Socket::CreateSocket(col->node, UdpSocketFactory::GetTypeId());
        col->udp->Bind(Inet6SocketAddress(Ipv6Address::GetAny(), 9000));
        col->udp->SetRecvCallback(MakeCallback(&Collector::OnReport, col));
        col->bcast = Socket::CreateSocket(col->node, UdpSocketFactory::GetTypeId());
        col->bcast->Bind(Inet6SocketAddress(Ipv6Address::GetAny(), 0));
        col->bcast->BindToNetDevice(sixDev.Get(0));
        g_cols.push_back(col);

        Ipv6Address colAddr = ifs.GetAddress(0, 1);
        for (uint32_t i = 0; i < n; ++i)
        {
            auto* s = new Sensor();
            s->id = sid++;
            s->pond = p;
            s->node = sens.Get(i);
            g_sensorNodeIds.insert(s->node->GetId());
            s->colAddr = colAddr;
            s->rv = CreateObject<UniformRandomVariable>();
            s->rv->SetStream(stream++);
            s->tx = Socket::CreateSocket(s->node, UdpSocketFactory::GetTypeId());
            s->tx->Bind(Inet6SocketAddress(Ipv6Address::GetAny(), 0));
            s->rxBeacon = Socket::CreateSocket(s->node, UdpSocketFactory::GetTypeId());
            s->rxBeacon->Bind(Inet6SocketAddress(Ipv6Address::GetAny(), 9001));
            s->rxBeacon->SetRecvCallback(MakeCallback(&Sensor::OnBeacon, s));
            g_sensors.push_back(s);
        }
        if (C.outsiderRate > 0)
        { // outsider: forged reports with invalid link MAC, Poisson
            Ptr<Socket> os = Socket::CreateSocket(outsider.Get(0), UdpSocketFactory::GetTypeId());
            os->Bind(Inet6SocketAddress(Ipv6Address::GetAny(), 0));
            Ptr<ExponentialRandomVariable> ex = CreateObject<ExponentialRandomVariable>();
            ex->SetAttribute("Mean", DoubleValue(1.0 / C.outsiderRate));
            ex->SetStream(stream++);
            std::function<void()> fire;
            auto firePtr = std::make_shared<std::function<void()>>();
            *firePtr = [os, colAddr, ex, firePtr]() {
                if (Simulator::Now().GetSeconds() > C.simTime - C.drain)
                    return;
                Rec r{999999, 0, 0, 0, 0, 1, 0};
                std::vector<uint8_t> meta;
                Put(meta, r);
                meta.push_back(0); // bad MAC
                auto b = MakeBuf(M_REPORT, meta, ReportSize());
                os->SendTo(Create<Packet>(b.data(), b.size()), 0, Inet6SocketAddress(colAddr, 9000));
                Simulator::Schedule(Seconds(ex->GetValue()), *firePtr);
            };
            Simulator::Schedule(Seconds(C.attackStart), *firePtr);
        }
    }
    // attackers: first `attackers` sensors spread across ponds (round robin)
    for (uint32_t k = 0; k < C.attackers && k < g_sensors.size(); ++k)
        g_sensors[(k * C.perPond + k / P) % g_sensors.size()]->attacker = true;

    // ---------------- station / BE / TCP wiring
    g_st = new Station();
    g_st->node = stNode.Get(0);
    g_be = new BackEnd();
    g_be->node = beNode.Get(0);
    g_be->rv = CreateObject<UniformRandomVariable>();
    g_be->rv->SetStream(stream++);
    Ipv4Address stAddr = lanIf.GetAddress(P), beAddr = wanIf.GetAddress(1);

    // station listens for collector uplinks (port 7000); BE listens for station (port 7100);
    // collectors listen for station downlink (port 7200)
    Ptr<Socket> stListen = Socket::CreateSocket(g_st->node, TcpSocketFactory::GetTypeId());
    stListen->Bind(InetSocketAddress(Ipv4Address::GetAny(), 7000));
    stListen->Listen();
    stListen->SetAcceptCallback(MakeNullCallback<bool, Ptr<Socket>, const Address&>(),
                                MakeCallback(+[](Ptr<Socket> s, const Address&) {
                                    auto* l = new TcpLink();
                                    l->onMsg = [](const std::string& b) { g_st->OnUp(b); };
                                    l->Attach(s);
                                    g_st->fromCol.push_back(l);
                                }));
    Ptr<Socket> beListen = Socket::CreateSocket(g_be->node, TcpSocketFactory::GetTypeId());
    beListen->Bind(InetSocketAddress(Ipv4Address::GetAny(), 7100));
    beListen->Listen();
    beListen->SetAcceptCallback(MakeNullCallback<bool, Ptr<Socket>, const Address&>(),
                                MakeCallback(+[](Ptr<Socket> s, const Address&) {
                                    g_be->fromSt.onMsg = [](const std::string& b) { g_be->OnSite(b); };
                                    g_be->fromSt.Attach(s);
                                }));
    for (auto* col : g_cols)
    {
        Ptr<Socket> l = Socket::CreateSocket(col->node, TcpSocketFactory::GetTypeId());
        l->Bind(InetSocketAddress(Ipv4Address::GetAny(), 7200));
        l->Listen();
        l->SetAcceptCallback(MakeNullCallback<bool, Ptr<Socket>, const Address&>(),
                             MakeCallback(+[](Ptr<Socket> s, const Address& from) {
                                 // identify collector by local node
                                 for (auto* c : g_cols)
                                     if (c->node == s->GetNode())
                                     {
                                         c->down.onMsg = [c](const std::string& b) { c->OnDown(b); };
                                         c->down.Attach(s);
                                     }
                             }));
        Simulator::Schedule(Seconds(0.1), [col, stAddr]() {
            Ptr<Socket> s = Socket::CreateSocket(col->node, TcpSocketFactory::GetTypeId());
            s->Bind();
            col->up.Attach(s);
            s->Connect(InetSocketAddress(stAddr, 7000));
        });
        Simulator::Schedule(Seconds(0.1), [col, lanIf]() {
            Ptr<Socket> s = Socket::CreateSocket(g_st->node, TcpSocketFactory::GetTypeId());
            s->Bind();
            auto* link = new TcpLink();
            link->Attach(s);
            g_st->toCol.push_back(link);
            s->Connect(InetSocketAddress(lanIf.GetAddress(col->id), 7200));
        });
    }
    Simulator::Schedule(Seconds(0.1), [beAddr]() {
        Ptr<Socket> s = Socket::CreateSocket(g_st->node, TcpSocketFactory::GetTypeId());
        s->Bind();
        g_st->toBe.onMsg = [](const std::string& b) { g_st->OnUp(b); };
        g_st->toBe.Attach(s);
        s->Connect(InetSocketAddress(beAddr, 7100));
    });
    Simulator::Schedule(Seconds(0.5), &Station::Beacon, g_st);
    Simulator::Schedule(Seconds(0.75), &Station::Flush, g_st);
    for (auto* s : g_sensors)
        s->Start(1.0 + s->rv->GetValue(0, C.reportInterval));
    if (C.byzNoticeRate > 0)
    {
        static Ptr<UniformRandomVariable> byzRv = CreateObject<UniformRandomVariable>();
        byzRv->SetStream(stream++);
        static std::function<void()> byz;
        byz = []() {
            if (Simulator::Now().GetSeconds() < C.simTime - C.drain)
                Simulator::Schedule(Seconds(1.0 / C.byzNoticeRate), byz);
            // accuse a random honest sensor (the collector holds its link key but not its ratchet state)
            for (int tries = 0; tries < 100; ++tries)
            {
                uint32_t v = byzRv->GetInteger(0, g_sensors.size() - 1);
                if (!g_sensors[v]->attacker)
                {
                    g_cols[0]->Notice(v);
                    break;
                }
            }
        };
        Simulator::Schedule(Seconds(C.attackStart), byz);
    }
    // sensor window coverage: at each window midpoint, count sensors holding the current window
    for (double t = C.warmup + C.window / 2; t < C.simTime - C.drain; t += C.window)
        Simulator::Schedule(Seconds(t), []() {
            for (auto* s : g_sensors)
            {
                S.sensorWindows++;
                if (s->curWindow != (int64_t)g_st->window)
                    S.sensorWindowsMissed++;
            }
        });

    if (C.perReport)
    {
        std::string fn = C.out + "/perreport_" + C.tag + "_" + C.variant + "_run" + std::to_string(C.run) + ".csv";
        g_perRep.open(fn);
        g_perRep << "sensor,gen,delay\n";
    }
    Simulator::Stop(Seconds(C.simTime));
    Simulator::Run();

    // ---------------- metrics
    double T = C.simTime - C.drain - C.warmup; // generation window used for rates
    double pdr = S.generated ? double(S.committed) / S.generated : NAN;
    double onTime = S.generated ? double(S.committed - S.committedLate) / S.generated : NAN;
    double jit = 0;
    uint64_t jn = 0;
    for (auto& [k, v] : S.perSensorDelay)
        for (size_t i = 1; i < v.size(); ++i)
        {
            jit += std::fabs(v[i] - v[i - 1]);
            jn++;
        }
    double colBusy = 0, colBusyMax = 0;
    for (auto* c : g_cols)
    {
        double u = c->cpu.busyTotal / (C.simTime - C.warmup);
        colBusy += u;
        colBusyMax = std::max(colBusyMax, u);
    }
    colBusy /= g_cols.size();
    // radio energy model (CC2420-class: TX 17.4 mA, RX 18.8 mA @ 3 V, 32 us/byte); RX counted for received frames only
    // (duty-cycled listening assumption); CPU energy ESP32 active 0.264 W.
    double eTx = S.sensorTxBytes * 32e-6 * 0.0174 * 3.0, eRx = S.sensorRxBytes * 32e-6 * 0.0188 * 3.0;
    double eCpu = S.sensorCpuMs * 1e-3 * 0.264;
    double perRepDen = std::max<uint64_t>(1, S.sent);
    double revProp = NAN, detMit = NAN;
    if (S.revIssue >= 0 && !S.revInstall.empty())
    {
        double last = 0;
        for (auto& [c, t] : S.revInstall)
            last = std::max(last, t);
        if (S.revInstall.size() == g_cols.size())
        {
            revProp = last - S.revIssue;
            detMit = last - S.firstInvalid;
        }
    }
    double airtimePond = (S.sensorTxBytes * 32e-6) / (T * P); // sensor-originated airtime fraction per pond
    std::string fn = C.out + "/summary.csv";
    bool exists = std::ifstream(fn).good();
    std::ofstream o(fn, std::ios::app);
    if (!exists)
        o << "tag,variant,run,nSensors,perPond,P,reportInterval,theta,radius,wanDelayMs,wanLoss,wanRate,attackers,"
             "attackRate,defenses,outsiderRate,burst,outage,generated,noBeacon,sent,committed,pdr,syncSuccess,"
             "deadlineMiss,e2eMean,e2eP50,e2eP95,e2eP99,e2eStd,jitter,authMean,authP95,throughputRps,"
             "goodputBps,sensorFramesPerReport,sensorBytesPerReport,airtimePerPond,lanBytesPerRep,wanBytesPerRep,"
             "macTxDrop,energyPerReport_mJ,energyTx_mJ,energyRx_mJ,energyCpu_mJ,colCpuUtil,colCpuUtilMax,"
             "meanBatch,testsPerVerified,hecmPerVerified,stHecmPerRep,beHecmPerRep,macDrop,windowDrop,"
             "replayDrop,quotaDrop,negDrop,revokedDrop,sigDrop,attackCommitted,firstInvalid,revIssue,"
             "revPropagation,detectToMitigate,rlBytes,windowMissFrac,falseRevoked,noticesRejected,noticesReceived,evidence,byzNoticeRate,sharedChannel,pondSpacing,tHecmSensor,tHecmCol,beaconStagger\n";
    double e2eMean = S.e2e.empty() ? NAN : std::accumulate(S.e2e.begin(), S.e2e.end(), 0.0) / S.e2e.size();
    double var = 0;
    for (double x : S.e2e)
        var += (x - e2eMean) * (x - e2eMean);
    double e2eStd = S.e2e.size() > 1 ? std::sqrt(var / (S.e2e.size() - 1)) : NAN;
    double authMean = S.auth.empty() ? NAN : std::accumulate(S.auth.begin(), S.auth.end(), 0.0) / S.auth.size();
    o << C.tag << "," << C.variant << "," << C.run << "," << C.nSensors << "," << C.perPond << "," << P << ","
      << C.reportInterval << "," << C.theta << "," << C.radius << "," << C.wanDelayMs << "," << C.wanLoss << ","
      << C.wanRate << "," << C.attackers << "," << C.attackRate << "," << C.defenses << "," << C.outsiderRate << ","
      << (C.burstStart >= 0) << "," << (C.wanOutageStart >= 0) << "," << S.generated << "," << S.noBeacon << ","
      << S.sent << "," << S.committed << "," << pdr << "," << onTime << "," << 1 - onTime << "," << e2eMean << ","
      << Pct(S.e2e, .5) << "," << Pct(S.e2e, .95) << "," << Pct(S.e2e, .99) << "," << e2eStd << ","
      << (jn ? jit / jn : NAN) << "," << authMean << "," << Pct(S.auth, .95) << "," << S.committed / T << ","
      << S.committed * 8.0 / T << "," << double(S.sensorTxFrames) / perRepDen << ","
      << double(S.sensorTxBytes) / perRepDen << "," << airtimePond << ","
      << double(S.lanBytes) / std::max<uint64_t>(1, S.committed) << ","
      << double(S.wanBytes) / std::max<uint64_t>(1, S.committed) << "," << S.macTxDrop << ","
      << (eTx + eRx + eCpu) * 1e3 / perRepDen << "," << eTx * 1e3 / perRepDen << "," << eRx * 1e3 / perRepDen << ","
      << eCpu * 1e3 / perRepDen << "," << colBusy << "," << colBusyMax << ","
      << (S.batches ? double(S.batchSizeSum) / S.batches : NAN) << ","
      << double(S.batchTests) / std::max<uint64_t>(1, S.verifiedOk) << ","
      << S.groupHecmCol / std::max<uint64_t>(1, S.verifiedOk) << "," << S.stHecm / std::max<uint64_t>(1, S.committed)
      << "," << S.beHecm / std::max<uint64_t>(1, S.committed) << "," << S.macDrop << "," << S.windowDrop << ","
      << S.replayDrop << "," << S.quotaDrop << "," << S.negDrop << "," << S.revokedDrop << "," << S.sigDrop << ","
      << S.attackCommitted << "," << S.firstInvalid << "," << S.revIssue << "," << revProp << "," << detMit << ","
      << S.rlBytes << "," << (S.sensorWindows ? double(S.sensorWindowsMissed) / S.sensorWindows : NAN) << ","
      << S.falseRevoked << "," << S.noticesRejected << "," << S.noticesReceived << "," << C.evidence << ","
      << C.byzNoticeRate << "," << C.sharedChannel << "," << C.pondSpacing << "," << C.tHecmSensor << "," << C.tHecmCol << "," << C.beaconStagger << "\n";
    Simulator::Destroy();
    return 0;
}
