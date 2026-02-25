#include "pwmb_geom/triangulate.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <set>
#include <utility>
#include <vector>

namespace pwmb_geom {

namespace {

constexpr double kEps = 1e-12;

using Segment2d = std::array<Point2d, 2>;

double cross(const Point2d& a, const Point2d& b, const Point2d& c) {
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
}

double signed_area(const Loop2d& loop) {
    long double area = 0.0;
    const std::size_t size = loop.size();
    for (std::size_t idx = 0; idx < size; ++idx) {
        const Point2d& p1 = loop[idx];
        const Point2d& p2 = loop[(idx + 1) % size];
        area += static_cast<long double>(p1[0] * p2[1] - p2[0] * p1[1]);
    }
    return static_cast<double>(0.5L * area);
}

bool points_equal(const Point2d& lhs, const Point2d& rhs, double eps = kEps) {
    return std::abs(lhs[0] - rhs[0]) <= eps && std::abs(lhs[1] - rhs[1]) <= eps;
}

bool point_on_segment(const Point2d& p, const Point2d& a, const Point2d& b, double eps = kEps) {
    const double cross_value = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
    if (std::abs(cross_value) > eps) {
        return false;
    }
    const double dot = (p[0] - a[0]) * (p[0] - b[0]) + (p[1] - a[1]) * (p[1] - b[1]);
    return dot <= eps;
}

Loop2d remove_duplicate_points(const Loop2d& loop) {
    if (loop.empty()) {
        return {};
    }
    Loop2d cleaned;
    cleaned.reserve(loop.size());
    cleaned.push_back(loop[0]);
    for (std::size_t idx = 1; idx < loop.size(); ++idx) {
        if (!points_equal(loop[idx], cleaned.back())) {
            cleaned.push_back(loop[idx]);
        }
    }
    if (cleaned.size() > 1 && points_equal(cleaned.front(), cleaned.back())) {
        cleaned.pop_back();
    }
    return cleaned;
}

Loop2d simplify_collinear(const Loop2d& loop, double eps = kEps) {
    if (loop.size() < 3) {
        return loop;
    }
    Loop2d points = loop;
    bool changed = true;
    while (changed && points.size() >= 3) {
        changed = false;
        Loop2d reduced;
        reduced.reserve(points.size());
        const std::size_t size = points.size();
        for (std::size_t idx = 0; idx < size; ++idx) {
            const Point2d& prev = points[(idx + size - 1) % size];
            const Point2d& curr = points[idx];
            const Point2d& next = points[(idx + 1) % size];
            if (std::abs(cross(prev, curr, next)) <= eps) {
                changed = true;
                continue;
            }
            reduced.push_back(curr);
        }
        if (reduced.size() < 3) {
            return {};
        }
        points = std::move(reduced);
    }
    return points;
}

Loop2d ensure_orientation(const Loop2d& loop, bool ccw) {
    const double area = signed_area(loop);
    if (ccw && area < 0.0) {
        return Loop2d(loop.rbegin(), loop.rend());
    }
    if (!ccw && area > 0.0) {
        return Loop2d(loop.rbegin(), loop.rend());
    }
    return loop;
}

std::vector<Segment2d> polygon_edges(const Loop2d& polygon) {
    std::vector<Segment2d> edges;
    edges.reserve(polygon.size());
    for (std::size_t idx = 0; idx < polygon.size(); ++idx) {
        edges.push_back(Segment2d{polygon[idx], polygon[(idx + 1) % polygon.size()]});
    }
    return edges;
}

int orientation(const Point2d& a, const Point2d& b, const Point2d& c, double eps = kEps) {
    const double value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1]);
    if (std::abs(value) <= eps) {
        return 0;
    }
    return value > 0.0 ? 1 : 2;
}

bool segments_intersect(const Point2d& p1, const Point2d& p2, const Point2d& q1, const Point2d& q2) {
    const int o1 = orientation(p1, p2, q1);
    const int o2 = orientation(p1, p2, q2);
    const int o3 = orientation(q1, q2, p1);
    const int o4 = orientation(q1, q2, p2);

    if (o1 != o2 && o3 != o4) {
        return true;
    }
    if (o1 == 0 && point_on_segment(q1, p1, p2)) {
        return true;
    }
    if (o2 == 0 && point_on_segment(q2, p1, p2)) {
        return true;
    }
    if (o3 == 0 && point_on_segment(p1, q1, q2)) {
        return true;
    }
    if (o4 == 0 && point_on_segment(p2, q1, q2)) {
        return true;
    }
    return false;
}

bool point_in_polygon(const Point2d& point, const Loop2d& polygon) {
    const double x = point[0];
    const double y = point[1];
    bool inside = false;
    const std::size_t size = polygon.size();
    for (std::size_t idx = 0; idx < size; ++idx) {
        const Point2d& p1 = polygon[idx];
        const Point2d& p2 = polygon[(idx + 1) % size];
        if (point_on_segment(point, p1, p2)) {
            return true;
        }
        const bool intersects = (p1[1] > y) != (p2[1] > y);
        if (!intersects) {
            continue;
        }
        const double x_intersect = ((p2[0] - p1[0]) * (y - p1[1]) / (p2[1] - p1[1])) + p1[0];
        if (x_intersect >= x) {
            inside = !inside;
        }
    }
    return inside;
}

bool point_in_triangle(const Point2d& point, const Triangle2d& triangle) {
    const Point2d& a = triangle[0];
    const Point2d& b = triangle[1];
    const Point2d& c = triangle[2];
    const double s1 = cross(point, a, b);
    const double s2 = cross(point, b, c);
    const double s3 = cross(point, c, a);
    const bool has_neg = (s1 < -kEps) || (s2 < -kEps) || (s3 < -kEps);
    const bool has_pos = (s1 > kEps) || (s2 > kEps) || (s3 > kEps);
    return !(has_neg && has_pos);
}

double dist2(const Point2d& a, const Point2d& b) {
    const double dx = a[0] - b[0];
    const double dy = a[1] - b[1];
    return dx * dx + dy * dy;
}

bool contains_touch(const std::vector<Point2d>& allowed_touch, const Point2d& p) {
    return std::any_of(allowed_touch.begin(), allowed_touch.end(), [&](const Point2d& candidate) {
        return points_equal(candidate, p);
    });
}

bool segment_crosses_edges(
    const Segment2d& segment,
    const std::vector<Segment2d>& edges,
    const std::vector<Point2d>& allowed_touch) {
    const Point2d& a1 = segment[0];
    const Point2d& a2 = segment[1];
    for (const Segment2d& edge : edges) {
        const Point2d& b1 = edge[0];
        const Point2d& b2 = edge[1];
        const bool shared_a1_b1 = points_equal(a1, b1);
        const bool shared_a1_b2 = points_equal(a1, b2);
        const bool shared_a2_b1 = points_equal(a2, b1);
        const bool shared_a2_b2 = points_equal(a2, b2);
        const bool shares_endpoint = shared_a1_b1 || shared_a1_b2 || shared_a2_b1 || shared_a2_b2;
        if (shares_endpoint) {
            const bool allowed =
                (!shared_a1_b1 || contains_touch(allowed_touch, a1)) &&
                (!shared_a1_b2 || contains_touch(allowed_touch, a1)) &&
                (!shared_a2_b1 || contains_touch(allowed_touch, a2)) &&
                (!shared_a2_b2 || contains_touch(allowed_touch, a2));
            if (allowed) {
                continue;
            }
        }
        if (segments_intersect(a1, a2, b1, b2)) {
            return true;
        }
    }
    return false;
}

int find_visible_vertex_index(const Loop2d& outer, const Loop2d& hole, int hole_index) {
    const Point2d& hole_vertex = hole[static_cast<std::size_t>(hole_index)];
    int best_idx = -1;
    double best_distance = std::numeric_limits<double>::infinity();
    const std::vector<Segment2d> outer_edges = polygon_edges(outer);
    const std::vector<Segment2d> hole_edges = polygon_edges(hole);

    for (std::size_t idx = 0; idx < outer.size(); ++idx) {
        const Point2d& candidate = outer[idx];
        if (points_equal(candidate, hole_vertex)) {
            continue;
        }
        const Segment2d segment{hole_vertex, candidate};
        if (segment_crosses_edges(segment, outer_edges, std::vector<Point2d>{candidate})) {
            continue;
        }
        const Point2d& hole_prev = hole[(static_cast<std::size_t>(hole_index) + hole.size() - 1) % hole.size()];
        const Point2d& hole_next = hole[(static_cast<std::size_t>(hole_index) + 1) % hole.size()];
        if (segment_crosses_edges(segment, hole_edges, std::vector<Point2d>{hole_vertex, hole_prev, hole_next})) {
            continue;
        }
        const Point2d midpoint{(hole_vertex[0] + candidate[0]) * 0.5, (hole_vertex[1] + candidate[1]) * 0.5};
        if (!point_in_polygon(midpoint, outer)) {
            continue;
        }
        if (point_in_polygon(midpoint, hole)) {
            continue;
        }
        const double distance = dist2(hole_vertex, candidate);
        if (distance < best_distance) {
            best_distance = distance;
            best_idx = static_cast<int>(idx);
        }
    }
    if (best_idx >= 0) {
        return best_idx;
    }
    if (outer.empty()) {
        return -1;
    }
    return static_cast<int>(std::min_element(outer.begin(), outer.end(), [&](const Point2d& lhs, const Point2d& rhs) {
        return dist2(hole_vertex, lhs) < dist2(hole_vertex, rhs);
    }) - outer.begin());
}

Loop2d merge_hole_into_polygon(const Loop2d& outer, const Loop2d& hole) {
    if (outer.size() < 3 || hole.size() < 3) {
        return {};
    }
    int hole_index = 0;
    for (std::size_t idx = 1; idx < hole.size(); ++idx) {
        const Point2d& lhs = hole[idx];
        const Point2d& rhs = hole[static_cast<std::size_t>(hole_index)];
        if ((lhs[0] > rhs[0]) || (std::abs(lhs[0] - rhs[0]) <= kEps && lhs[1] < rhs[1])) {
            hole_index = static_cast<int>(idx);
        }
    }
    const int outer_index = find_visible_vertex_index(outer, hole, hole_index);
    if (outer_index < 0) {
        return {};
    }

    Loop2d outer_rot;
    outer_rot.reserve(outer.size());
    for (std::size_t i = 0; i < outer.size(); ++i) {
        outer_rot.push_back(outer[(static_cast<std::size_t>(outer_index) + i) % outer.size()]);
    }

    Loop2d hole_rot;
    hole_rot.reserve(hole.size());
    for (std::size_t i = 0; i < hole.size(); ++i) {
        hole_rot.push_back(hole[(static_cast<std::size_t>(hole_index) + i) % hole.size()]);
    }

    Loop2d merged;
    merged.reserve(outer_rot.size() + hole_rot.size() + 3);
    merged.push_back(outer_rot[0]);
    merged.insert(merged.end(), hole_rot.begin(), hole_rot.end());
    merged.push_back(hole_rot[0]);
    merged.push_back(outer_rot[0]);
    merged.insert(merged.end(), outer_rot.begin() + 1, outer_rot.end());
    merged = simplify_collinear(remove_duplicate_points(merged));
    if (merged.size() < 3 || std::abs(signed_area(merged)) <= kEps) {
        return {};
    }
    return ensure_orientation(merged, true);
}

bool loops_are_axis_aligned(const std::vector<Loop2d>& loops, double eps = kEps) {
    for (const Loop2d& loop : loops) {
        if (loop.size() < 3) {
            return false;
        }
        for (std::size_t idx = 0; idx < loop.size(); ++idx) {
            const Point2d& p1 = loop[idx];
            const Point2d& p2 = loop[(idx + 1) % loop.size()];
            if (std::abs(p1[0] - p2[0]) > eps && std::abs(p1[1] - p2[1]) > eps) {
                return false;
            }
        }
    }
    return true;
}

std::vector<Triangle2d> triangulate_axis_aligned_loops(const std::vector<Loop2d>& loops) {
    std::set<double> y_values_set;
    for (const Loop2d& loop : loops) {
        for (const Point2d& point : loop) {
            y_values_set.insert(point[1]);
        }
    }
    const std::vector<double> y_values(y_values_set.begin(), y_values_set.end());
    if (y_values.size() < 2) {
        return {};
    }

    std::vector<Triangle2d> triangles;
    for (std::size_t idx = 0; idx + 1 < y_values.size(); ++idx) {
        const double y0 = y_values[idx];
        const double y1 = y_values[idx + 1];
        if ((y1 - y0) <= kEps) {
            continue;
        }
        const double y_mid = (y0 + y1) * 0.5;
        std::vector<double> x_intersections;

        for (const Loop2d& loop : loops) {
            for (std::size_t edge_idx = 0; edge_idx < loop.size(); ++edge_idx) {
                const Point2d& p1 = loop[edge_idx];
                const Point2d& p2 = loop[(edge_idx + 1) % loop.size()];
                if (std::abs(p1[1] - p2[1]) <= kEps) {
                    continue;
                }
                const double y_min = std::min(p1[1], p2[1]);
                const double y_max = std::max(p1[1], p2[1]);
                if (y_mid < y_min || y_mid >= y_max) {
                    continue;
                }
                const double x = p1[0] + (y_mid - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1]);
                x_intersections.push_back(x);
            }
        }
        std::sort(x_intersections.begin(), x_intersections.end());
        const std::size_t pair_count = x_intersections.size() / 2;
        for (std::size_t pair_idx = 0; pair_idx < pair_count; ++pair_idx) {
            const double x0 = x_intersections[pair_idx * 2];
            const double x1 = x_intersections[pair_idx * 2 + 1];
            if ((x1 - x0) <= kEps) {
                continue;
            }
            triangles.push_back(Triangle2d{Point2d{x0, y0}, Point2d{x1, y0}, Point2d{x1, y1}});
            triangles.push_back(Triangle2d{Point2d{x0, y0}, Point2d{x1, y1}, Point2d{x0, y1}});
        }
    }
    return triangles;
}

double x_at_y(const Point2d& p1, const Point2d& p2, double y) {
    const double y1 = p1[1];
    const double y2 = p2[1];
    if (std::abs(y2 - y1) <= kEps) {
        return std::min(p1[0], p2[0]);
    }
    const double t = (y - y1) / (y2 - y1);
    return p1[0] + t * (p2[0] - p1[0]);
}

std::vector<Triangle2d> triangulate_scanline_loops(const std::vector<Loop2d>& loops) {
    std::set<double> y_values_set;
    for (const Loop2d& loop : loops) {
        for (const Point2d& point : loop) {
            y_values_set.insert(point[1]);
        }
    }
    const std::vector<double> y_values(y_values_set.begin(), y_values_set.end());
    if (y_values.size() < 2) {
        return {};
    }

    std::vector<Triangle2d> triangles;
    for (std::size_t idx = 0; idx + 1 < y_values.size(); ++idx) {
        const double y0 = y_values[idx];
        const double y1 = y_values[idx + 1];
        if ((y1 - y0) <= kEps) {
            continue;
        }
        const double y_mid = (y0 + y1) * 0.5;
        std::vector<std::pair<double, Segment2d>> crossings;

        for (const Loop2d& loop : loops) {
            for (std::size_t edge_idx = 0; edge_idx < loop.size(); ++edge_idx) {
                const Point2d& p1 = loop[edge_idx];
                const Point2d& p2 = loop[(edge_idx + 1) % loop.size()];
                if (std::abs(p1[1] - p2[1]) <= kEps) {
                    continue;
                }
                const double edge_y_min = std::min(p1[1], p2[1]);
                const double edge_y_max = std::max(p1[1], p2[1]);
                if (edge_y_max <= y0 || edge_y_min >= y1) {
                    continue;
                }
                crossings.push_back(std::make_pair(x_at_y(p1, p2, y_mid), Segment2d{p1, p2}));
            }
        }

        std::sort(crossings.begin(), crossings.end(), [](const auto& lhs, const auto& rhs) {
            return lhs.first < rhs.first;
        });
        const std::size_t pair_count = crossings.size() / 2;
        for (std::size_t pair_idx = 0; pair_idx < pair_count; ++pair_idx) {
            const Segment2d& left_edge = crossings[pair_idx * 2].second;
            const Segment2d& right_edge = crossings[pair_idx * 2 + 1].second;

            const double xl0 = x_at_y(left_edge[0], left_edge[1], y0);
            const double xl1 = x_at_y(left_edge[0], left_edge[1], y1);
            const double xr0 = x_at_y(right_edge[0], right_edge[1], y0);
            const double xr1 = x_at_y(right_edge[0], right_edge[1], y1);

            const Triangle2d tri1{Point2d{xl0, y0}, Point2d{xr0, y0}, Point2d{xr1, y1}};
            const Triangle2d tri2{Point2d{xl0, y0}, Point2d{xr1, y1}, Point2d{xl1, y1}};
            if (std::abs(cross(tri1[0], tri1[1], tri1[2])) > kEps) {
                triangles.push_back(tri1);
            }
            if (std::abs(cross(tri2[0], tri2[1], tri2[2])) > kEps) {
                triangles.push_back(tri2);
            }
        }
    }
    return triangles;
}

std::vector<Triangle2d> ear_clip(const Loop2d& polygon) {
    Loop2d vertices = simplify_collinear(remove_duplicate_points(polygon));
    if (vertices.size() < 3) {
        return {};
    }
    vertices = ensure_orientation(vertices, true);
    std::vector<int> indices(vertices.size());
    for (std::size_t idx = 0; idx < vertices.size(); ++idx) {
        indices[idx] = static_cast<int>(idx);
    }

    std::vector<Triangle2d> triangles;
    int guard = 0;
    const int max_guard = std::max(1'000, static_cast<int>(indices.size() * indices.size() * 4));
    while (indices.size() > 3 && guard < max_guard) {
        ++guard;
        bool ear_found = false;
        for (std::size_t i = 0; i < indices.size(); ++i) {
            const int i_prev = indices[(i + indices.size() - 1) % indices.size()];
            const int i_curr = indices[i];
            const int i_next = indices[(i + 1) % indices.size()];
            const Point2d& prev = vertices[static_cast<std::size_t>(i_prev)];
            const Point2d& curr = vertices[static_cast<std::size_t>(i_curr)];
            const Point2d& next = vertices[static_cast<std::size_t>(i_next)];

            if (cross(prev, curr, next) <= kEps) {
                continue;
            }
            const Triangle2d ear{prev, curr, next};
            bool contains = false;
            for (int idx : indices) {
                if (idx == i_prev || idx == i_curr || idx == i_next) {
                    continue;
                }
                if (point_in_triangle(vertices[static_cast<std::size_t>(idx)], ear)) {
                    contains = true;
                    break;
                }
            }
            if (contains) {
                continue;
            }
            triangles.push_back(ear);
            indices.erase(indices.begin() + static_cast<std::ptrdiff_t>(i));
            ear_found = true;
            break;
        }
        if (!ear_found) {
            break;
        }
    }

    if (indices.size() == 3) {
        triangles.push_back(Triangle2d{
            vertices[static_cast<std::size_t>(indices[0])],
            vertices[static_cast<std::size_t>(indices[1])],
            vertices[static_cast<std::size_t>(indices[2])],
        });
    } else if (indices.size() > 3) {
        const int root = indices[0];
        for (std::size_t i = 1; i + 1 < indices.size(); ++i) {
            triangles.push_back(Triangle2d{
                vertices[static_cast<std::size_t>(root)],
                vertices[static_cast<std::size_t>(indices[i])],
                vertices[static_cast<std::size_t>(indices[i + 1])],
            });
        }
    }

    std::vector<Triangle2d> filtered;
    filtered.reserve(triangles.size());
    for (const Triangle2d& tri : triangles) {
        if (std::abs(cross(tri[0], tri[1], tri[2])) > kEps) {
            filtered.push_back(tri);
        }
    }
    return filtered;
}

}  // namespace

std::vector<Triangle2d> triangulate_polygon_with_holes(const Loop2d& outer, const std::vector<Loop2d>& holes) {
    if (outer.size() < 3) {
        return {};
    }
    std::vector<Loop2d> loops;
    loops.reserve(holes.size() + 1);
    loops.push_back(outer);
    for (const Loop2d& hole : holes) {
        if (hole.size() >= 3) {
            loops.push_back(hole);
        }
    }
    if (loops_are_axis_aligned(loops)) {
        return triangulate_axis_aligned_loops(loops);
    }

    const std::vector<Triangle2d> scanline = triangulate_scanline_loops(loops);
    if (!scanline.empty()) {
        return scanline;
    }

    Loop2d polygon = ensure_orientation(outer, true);
    for (const Loop2d& hole : holes) {
        if (hole.size() < 3) {
            continue;
        }
        const Loop2d hole_cw = ensure_orientation(hole, false);
        const Loop2d merged = merge_hole_into_polygon(polygon, hole_cw);
        if (merged.empty()) {
            continue;
        }
        polygon = merged;
    }
    const std::vector<Triangle2d> ear = ear_clip(polygon);
    if (!ear.empty()) {
        return ear;
    }
    return triangulate_scanline_loops(loops);
}

}  // namespace pwmb_geom
