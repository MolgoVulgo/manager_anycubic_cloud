#include "pwmb_geom/extract_polygons.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#ifdef PWMB_GEOM_WITH_OPENCV
#include <opencv2/imgproc.hpp>
#endif

namespace pwmb_geom {

namespace {

using PointKey = std::uint64_t;

struct EdgeKey {
    PointKey a;
    PointKey b;

    bool operator==(const EdgeKey& other) const noexcept { return a == other.a && b == other.b; }
};

struct EdgeKeyHash {
    std::size_t operator()(const EdgeKey& key) const noexcept {
        return static_cast<std::size_t>((key.a * 1315423911ULL) ^ (key.b + 0x9e3779b97f4a7c15ULL));
    }
};

struct DirectedEdgeKey {
    PointKey from;
    PointKey to;

    bool operator==(const DirectedEdgeKey& other) const noexcept { return from == other.from && to == other.to; }
};

struct DirectedEdgeKeyHash {
    std::size_t operator()(const DirectedEdgeKey& key) const noexcept {
        return static_cast<std::size_t>((key.from * 2654435761ULL) ^ (key.to + 0x517cc1b727220a95ULL));
    }
};

using OutgoingMap = std::unordered_map<PointKey, std::vector<PointKey>>;
using UsedEdgeSet = std::unordered_set<DirectedEdgeKey, DirectedEdgeKeyHash>;

PointKey encode_point(int x, int y) {
    return (static_cast<PointKey>(static_cast<std::uint32_t>(x)) << 32) |
           static_cast<PointKey>(static_cast<std::uint32_t>(y));
}

Point2i decode_point(PointKey key) {
    const auto x = static_cast<std::int32_t>(key >> 32);
    const auto y = static_cast<std::int32_t>(key & 0xFFFFFFFFULL);
    return {static_cast<int>(x), static_cast<int>(y)};
}

EdgeKey make_undirected(PointKey p1, PointKey p2) {
    if (p1 <= p2) {
        return EdgeKey{p1, p2};
    }
    return EdgeKey{p2, p1};
}

int direction_rank(int dx, int dy) {
    if (dx > 0 && dy == 0) {
        return 0;
    }
    if (dx == 0 && dy > 0) {
        return 1;
    }
    if (dx < 0 && dy == 0) {
        return 2;
    }
    if (dx == 0 && dy < 0) {
        return 3;
    }
    return 4;
}

bool is_collinear(const Point2i& a, const Point2i& b, const Point2i& c) {
    return (b[0] - a[0]) * (c[1] - b[1]) == (b[1] - a[1]) * (c[0] - b[0]);
}

double signed_area(const std::vector<PointKey>& loop) {
    long double area = 0.0;
    const std::size_t size = loop.size();
    for (std::size_t i = 0; i < size; ++i) {
        const Point2i p1 = decode_point(loop[i]);
        const Point2i p2 = decode_point(loop[(i + 1) % size]);
        area += static_cast<long double>(p1[0] * p2[1] - p2[0] * p1[1]);
    }
    return static_cast<double>(0.5L * area);
}

std::vector<PointKey> simplify_collinear(const std::vector<PointKey>& loop) {
    if (loop.size() < 3) {
        return loop;
    }
    std::vector<PointKey> points = loop;
    bool changed = true;
    while (changed && points.size() >= 3) {
        changed = false;
        std::vector<PointKey> simplified;
        simplified.reserve(points.size());
        const std::size_t size = points.size();
        for (std::size_t idx = 0; idx < size; ++idx) {
            const Point2i prev = decode_point(points[(idx + size - 1) % size]);
            const Point2i curr = decode_point(points[idx]);
            const Point2i next = decode_point(points[(idx + 1) % size]);
            if (is_collinear(prev, curr, next)) {
                changed = true;
                continue;
            }
            simplified.push_back(points[idx]);
        }
        if (simplified.size() < 3) {
            return {};
        }
        points = std::move(simplified);
    }
    return points;
}

PointKey pick_next_point(PointKey prev, PointKey current, const std::vector<PointKey>& candidates) {
    if (candidates.size() == 1) {
        return candidates[0];
    }
    const Point2i prev_point = decode_point(prev);
    const Point2i current_point = decode_point(current);
    const int in_dx = current_point[0] - prev_point[0];
    const int in_dy = current_point[1] - prev_point[1];

    struct Score {
        int backtrack;
        int neg_turn;
        int rank;
        int x;
        int y;
    };

    PointKey best = candidates[0];
    Score best_score{};
    bool init = false;
    for (PointKey candidate : candidates) {
        const Point2i cand = decode_point(candidate);
        const int out_dx = cand[0] - current_point[0];
        const int out_dy = cand[1] - current_point[1];
        const int backtrack = (out_dx == -in_dx && out_dy == -in_dy) ? 1 : 0;
        const int turn = in_dx * out_dy - in_dy * out_dx;
        const Score score = {
            backtrack,
            -turn,
            direction_rank(out_dx, out_dy),
            cand[0],
            cand[1],
        };
        if (!init ||
            std::tie(score.backtrack, score.neg_turn, score.rank, score.x, score.y) <
                std::tie(best_score.backtrack, best_score.neg_turn, best_score.rank, best_score.x, best_score.y)) {
            best = candidate;
            best_score = score;
            init = true;
        }
    }
    return best;
}

std::vector<PointKey> trace_loop(
    PointKey start,
    PointKey end,
    const OutgoingMap& outgoing,
    UsedEdgeSet& used) {
    std::vector<PointKey> points;
    points.reserve(128);
    points.push_back(start);

    PointKey prev = start;
    PointKey current = end;
    used.insert(DirectedEdgeKey{start, end});

    int guard = 0;
    while (guard < 1'000'000) {
        ++guard;
        points.push_back(current);
        if (current == start) {
            points.pop_back();
            return points;
        }

        const auto out_it = outgoing.find(current);
        if (out_it == outgoing.end()) {
            return {};
        }
        std::vector<PointKey> candidates;
        candidates.reserve(out_it->second.size());
        for (PointKey candidate : out_it->second) {
            if (used.find(DirectedEdgeKey{current, candidate}) == used.end()) {
                candidates.push_back(candidate);
            }
        }
        if (candidates.empty()) {
            return {};
        }
        const PointKey next = pick_next_point(prev, current, candidates);
        used.insert(DirectedEdgeKey{current, next});
        prev = current;
        current = next;
    }
    return {};
}

Loop2i to_loop(const std::vector<PointKey>& encoded_loop) {
    Loop2i loop;
    loop.reserve(encoded_loop.size());
    for (PointKey encoded : encoded_loop) {
        const Point2i p = decode_point(encoded);
        loop.push_back({p[0], p[1]});
    }
    return loop;
}

PolygonSet classify_by_major_sign(std::vector<std::vector<PointKey>> loops) {
    struct LoopArea {
        std::vector<PointKey> loop;
        double area;
    };
    std::vector<LoopArea> loop_areas;
    loop_areas.reserve(loops.size());
    for (auto& loop : loops) {
        const double area = signed_area(loop);
        if (loop.size() >= 3 && std::fabs(area) > 0.0) {
            loop_areas.push_back(LoopArea{std::move(loop), area});
        }
    }

    PolygonSet output;
    if (loop_areas.empty()) {
        return output;
    }

    std::size_t major_index = 0;
    double major_abs = -std::numeric_limits<double>::infinity();
    for (std::size_t i = 0; i < loop_areas.size(); ++i) {
        const double abs_area = std::fabs(loop_areas[i].area);
        if (abs_area > major_abs) {
            major_abs = abs_area;
            major_index = i;
        }
    }
    const double major_sign = loop_areas[major_index].area >= 0.0 ? 1.0 : -1.0;

    output.outer.reserve(loop_areas.size());
    output.holes.reserve(loop_areas.size());
    for (auto& item : loop_areas) {
        const bool is_outer = (item.area >= 0.0 && major_sign > 0.0) || (item.area < 0.0 && major_sign < 0.0);
        if (is_outer) {
            output.outer.push_back(to_loop(item.loop));
            continue;
        }
        output.holes.push_back(to_loop(item.loop));
    }
    return output;
}

#ifdef PWMB_GEOM_WITH_OPENCV
int hierarchy_depth(int index, const std::vector<cv::Vec4i>& hierarchy) {
    int depth = 0;
    int parent = hierarchy[static_cast<std::size_t>(index)][3];
    int guard = 0;
    while (parent >= 0 && parent < static_cast<int>(hierarchy.size()) && guard < static_cast<int>(hierarchy.size())) {
        ++depth;
        parent = hierarchy[static_cast<std::size_t>(parent)][3];
        ++guard;
    }
    return depth;
}

std::vector<PointKey> contour_to_grid_loop(const std::vector<cv::Point>& contour, int width, int height) {
    std::vector<PointKey> encoded;
    encoded.reserve(contour.size());
    for (const cv::Point& point : contour) {
        int x = static_cast<int>(std::lround(static_cast<double>(point.x) * 0.5));
        int y = static_cast<int>(std::lround(static_cast<double>(point.y) * 0.5));
        x = std::clamp(x, 0, width);
        y = std::clamp(y, 0, height);
        const PointKey key = encode_point(x, y);
        if (encoded.empty() || encoded.back() != key) {
            encoded.push_back(key);
        }
    }
    if (encoded.size() >= 2 && encoded.front() == encoded.back()) {
        encoded.pop_back();
    }
    return encoded;
}

PolygonSet extract_polygons_opencv_impl(const std::uint8_t* data, int width, int height) {
    const int expanded_width = width * 2;
    const int expanded_height = height * 2;
    cv::Mat expanded(expanded_height, expanded_width, CV_8UC1, cv::Scalar(0));
    for (int y = 0; y < height; ++y) {
        const auto row_offset = static_cast<std::size_t>(y) * static_cast<std::size_t>(width);
        for (int x = 0; x < width; ++x) {
            if (data[row_offset + static_cast<std::size_t>(x)] == 0) {
                continue;
            }
            expanded(cv::Rect(x * 2, y * 2, 2, 2)).setTo(cv::Scalar(255));
        }
    }

    std::vector<std::vector<cv::Point>> contours;
    std::vector<cv::Vec4i> hierarchy;
    cv::findContours(expanded, contours, hierarchy, cv::RETR_CCOMP, cv::CHAIN_APPROX_SIMPLE);
    if (contours.empty()) {
        return {};
    }

    struct LoopWithDepth {
        std::vector<PointKey> loop;
        int depth;
    };
    std::vector<LoopWithDepth> loops;
    loops.reserve(contours.size());

    const bool has_hierarchy = hierarchy.size() == contours.size();
    for (std::size_t i = 0; i < contours.size(); ++i) {
        std::vector<PointKey> loop = contour_to_grid_loop(contours[i], width, height);
        if (loop.size() < 3) {
            continue;
        }
        loop = simplify_collinear(loop);
        if (loop.size() < 3 || std::fabs(signed_area(loop)) <= 0.0) {
            continue;
        }
        loops.push_back(LoopWithDepth{
            std::move(loop),
            has_hierarchy ? hierarchy_depth(static_cast<int>(i), hierarchy) : 0,
        });
    }
    if (loops.empty()) {
        return {};
    }
    if (!has_hierarchy) {
        std::vector<std::vector<PointKey>> fallback_loops;
        fallback_loops.reserve(loops.size());
        for (auto& item : loops) {
            fallback_loops.push_back(std::move(item.loop));
        }
        return classify_by_major_sign(std::move(fallback_loops));
    }

    PolygonSet output;
    output.outer.reserve(loops.size());
    output.holes.reserve(loops.size());
    for (const auto& item : loops) {
        if ((item.depth & 1) == 0) {
            output.outer.push_back(to_loop(item.loop));
        } else {
            output.holes.push_back(to_loop(item.loop));
        }
    }
    return output;
}
#endif

PolygonSet extract_polygons_native_impl(const std::uint8_t* data, int width, int height) {
    std::unordered_map<EdgeKey, std::pair<PointKey, PointKey>, EdgeKeyHash> edges;
    edges.reserve(static_cast<std::size_t>(width) * static_cast<std::size_t>(height));

    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            if (data[static_cast<std::size_t>(y) * static_cast<std::size_t>(width) + static_cast<std::size_t>(x)] == 0) {
                continue;
            }
            const PointKey p00 = encode_point(x, y);
            const PointKey p10 = encode_point(x + 1, y);
            const PointKey p11 = encode_point(x + 1, y + 1);
            const PointKey p01 = encode_point(x, y + 1);
            const std::pair<PointKey, PointKey> directed_edges[4] = {
                {p00, p10},
                {p10, p11},
                {p11, p01},
                {p01, p00},
            };
            for (const auto& edge : directed_edges) {
                const EdgeKey key = make_undirected(edge.first, edge.second);
                const auto existing = edges.find(key);
                if (existing != edges.end()) {
                    edges.erase(existing);
                } else {
                    edges.emplace(key, edge);
                }
            }
        }
    }

    OutgoingMap outgoing;
    outgoing.reserve(edges.size());
    for (const auto& entry : edges) {
        const auto& edge = entry.second;
        outgoing[edge.first].push_back(edge.second);
    }

    UsedEdgeSet used;
    used.reserve(edges.size());
    std::vector<std::vector<PointKey>> loops;
    loops.reserve(edges.size() / 2 + 1);
    for (const auto& item : outgoing) {
        const PointKey start = item.first;
        for (PointKey target : item.second) {
            if (used.find(DirectedEdgeKey{start, target}) != used.end()) {
                continue;
            }
            std::vector<PointKey> loop = trace_loop(start, target, outgoing, used);
            if (loop.size() < 3) {
                continue;
            }
            std::vector<PointKey> simplified = simplify_collinear(loop);
            if (simplified.size() >= 3 && std::fabs(signed_area(simplified)) > 0.0) {
                loops.push_back(std::move(simplified));
            }
        }
    }
    return classify_by_major_sign(std::move(loops));
}

}  // namespace

PolygonSet extract_polygons(const std::uint8_t* data, int width, int height, ContourImpl impl) {
    if (data == nullptr) {
        throw std::invalid_argument("extract_polygons: null mask pointer");
    }
    if (width <= 0 || height <= 0) {
        throw std::invalid_argument("extract_polygons: invalid mask shape");
    }

    switch (impl) {
        case ContourImpl::kNative:
            return extract_polygons_native_impl(data, width, height);
        case ContourImpl::kOpenCV:
#ifdef PWMB_GEOM_WITH_OPENCV
            return extract_polygons_opencv_impl(data, width, height);
#else
            throw std::runtime_error(
                "extract_polygons: OpenCV contours requested but module was built without WITH_OPENCV");
#endif
    }
    return extract_polygons_native_impl(data, width, height);
}

bool opencv_contours_available() noexcept {
#ifdef PWMB_GEOM_WITH_OPENCV
    return true;
#else
    return false;
#endif
}

}  // namespace pwmb_geom
