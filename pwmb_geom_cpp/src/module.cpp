#include "pwmb_geom/extract_polygons.hpp"
#include "pwmb_geom/triangulate.hpp"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

namespace {

pwmb_geom::ContourImpl parse_impl(std::string impl) {
    std::transform(impl.begin(), impl.end(), impl.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    if (impl == "native") {
        return pwmb_geom::ContourImpl::kNative;
    }
    if (impl == "opencv") {
        return pwmb_geom::ContourImpl::kOpenCV;
    }
    if (impl == "auto") {
        return pwmb_geom::opencv_contours_available() ? pwmb_geom::ContourImpl::kOpenCV
                                                      : pwmb_geom::ContourImpl::kNative;
    }
    throw std::invalid_argument("extract_polygons: invalid impl (expected native|opencv|auto)");
}

py::dict extract_polygons_py(
    const py::array_t<std::uint8_t, py::array::c_style | py::array::forcecast>& mask,
    const std::string& impl) {
    const py::buffer_info info = mask.request();
    if (info.ndim != 2) {
        throw std::invalid_argument("extract_polygons expects a 2D uint8 mask");
    }
    if (info.shape[0] <= 0 || info.shape[1] <= 0) {
        throw std::invalid_argument("extract_polygons expects a non-empty mask");
    }
    const auto* data = static_cast<const std::uint8_t*>(info.ptr);
    const int height = static_cast<int>(info.shape[0]);
    const int width = static_cast<int>(info.shape[1]);
    const pwmb_geom::ContourImpl selected_impl = parse_impl(impl);
    const pwmb_geom::PolygonSet polygons = pwmb_geom::extract_polygons(data, width, height, selected_impl);

    py::dict payload;
    payload["outer"] = polygons.outer;
    payload["holes"] = polygons.holes;
    return payload;
}

std::vector<pwmb_geom::Point2d> parse_loop(const py::object& raw_loop) {
    std::vector<pwmb_geom::Point2d> loop;
    const py::sequence seq = py::reinterpret_borrow<py::sequence>(raw_loop);
    loop.reserve(seq.size());
    for (const py::handle point_handle : seq) {
        const py::sequence point_seq = py::reinterpret_borrow<py::sequence>(point_handle);
        if (point_seq.size() != 2) {
            continue;
        }
        loop.push_back(pwmb_geom::Point2d{
            py::cast<double>(point_seq[0]),
            py::cast<double>(point_seq[1]),
        });
    }
    return loop;
}

py::list triangulate_polygon_with_holes_py(const py::object& raw_outer, const py::object& raw_holes) {
    const std::vector<pwmb_geom::Point2d> outer = parse_loop(raw_outer);
    std::vector<std::vector<pwmb_geom::Point2d>> holes;
    const py::sequence holes_seq = py::reinterpret_borrow<py::sequence>(raw_holes);
    holes.reserve(holes_seq.size());
    for (const py::handle hole_handle : holes_seq) {
        holes.push_back(parse_loop(py::reinterpret_borrow<py::object>(hole_handle)));
    }
    const std::vector<pwmb_geom::Triangle2d> triangles = pwmb_geom::triangulate_polygon_with_holes(outer, holes);
    py::list payload;
    for (const auto& triangle : triangles) {
        py::list tri;
        for (const auto& point : triangle) {
            tri.append(py::make_tuple(point[0], point[1]));
        }
        payload.append(std::move(tri));
    }
    return payload;
}

struct PointKey {
    std::uint64_t x_bits;
    std::uint64_t y_bits;

    bool operator==(const PointKey& other) const noexcept {
        return x_bits == other.x_bits && y_bits == other.y_bits;
    }
};

struct PointKeyHash {
    std::size_t operator()(const PointKey& key) const noexcept {
        return static_cast<std::size_t>((key.x_bits * 1315423911ULL) ^ (key.y_bits + 0x9e3779b97f4a7c15ULL));
    }
};

PointKey make_point_key(const pwmb_geom::Point2d& point) {
    std::uint64_t x_bits = 0;
    std::uint64_t y_bits = 0;
    static_assert(sizeof(double) == sizeof(std::uint64_t), "unexpected double size");
    std::memcpy(&x_bits, &point[0], sizeof(double));
    std::memcpy(&y_bits, &point[1], sizeof(double));
    return PointKey{x_bits, y_bits};
}

py::dict triangulate_polygon_with_holes_indexed_py(
    const py::object& raw_outer,
    const py::object& raw_holes) {
    const std::vector<pwmb_geom::Point2d> outer = parse_loop(raw_outer);
    std::vector<std::vector<pwmb_geom::Point2d>> holes;
    const py::sequence holes_seq = py::reinterpret_borrow<py::sequence>(raw_holes);
    holes.reserve(holes_seq.size());
    for (const py::handle hole_handle : holes_seq) {
        holes.push_back(parse_loop(py::reinterpret_borrow<py::object>(hole_handle)));
    }
    const std::vector<pwmb_geom::Triangle2d> triangles = pwmb_geom::triangulate_polygon_with_holes(outer, holes);

    std::vector<float> vertices;
    std::vector<std::uint32_t> indices;
    vertices.reserve(triangles.size() * 3 * 2);
    indices.reserve(triangles.size() * 3);
    std::unordered_map<PointKey, std::uint32_t, PointKeyHash> point_index;
    point_index.reserve(triangles.size() * 3);

    auto index_for_point = [&](const pwmb_geom::Point2d& point) -> std::uint32_t {
        const PointKey key = make_point_key(point);
        const auto found = point_index.find(key);
        if (found != point_index.end()) {
            return found->second;
        }
        const std::uint32_t index = static_cast<std::uint32_t>(vertices.size() / 2);
        vertices.push_back(static_cast<float>(point[0]));
        vertices.push_back(static_cast<float>(point[1]));
        point_index.emplace(key, index);
        return index;
    };

    for (const auto& triangle : triangles) {
        for (const auto& point : triangle) {
            indices.push_back(index_for_point(point));
        }
    }

    py::array_t<float> vertices_array({static_cast<py::ssize_t>(vertices.size() / 2), static_cast<py::ssize_t>(2)});
    if (!vertices.empty()) {
        std::memcpy(vertices_array.mutable_data(), vertices.data(), vertices.size() * sizeof(float));
    }
    py::array_t<std::uint32_t> indices_array(
        {static_cast<py::ssize_t>(indices.size() / 3), static_cast<py::ssize_t>(3)});
    if (!indices.empty()) {
        std::memcpy(indices_array.mutable_data(), indices.data(), indices.size() * sizeof(std::uint32_t));
    }

    py::dict payload;
    payload["vertices"] = std::move(vertices_array);
    payload["indices"] = std::move(indices_array);
    return payload;
}

}  // namespace

PYBIND11_MODULE(_pwmb_geom, module) {
    module.doc() = "PWMB contour extraction native helpers";
    module.def("extract_polygons", &extract_polygons_py, py::arg("mask"), py::arg("impl") = "native");
    module.def("has_opencv_contours", []() { return pwmb_geom::opencv_contours_available(); });
    module.def(
        "triangulate_polygon_with_holes",
        &triangulate_polygon_with_holes_py,
        py::arg("outer"),
        py::arg("holes"));
    module.def(
        "triangulate_polygon_with_holes_indexed",
        &triangulate_polygon_with_holes_indexed_py,
        py::arg("outer"),
        py::arg("holes"));
}
