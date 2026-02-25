#include "pwmb_geom/extract_polygons.hpp"

#include <cstdint>
#include <stdexcept>

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;

namespace {

py::dict extract_polygons_py(const py::array_t<std::uint8_t, py::array::c_style | py::array::forcecast>& mask) {
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
    const pwmb_geom::PolygonSet polygons = pwmb_geom::extract_polygons(data, width, height);

    py::dict payload;
    payload["outer"] = polygons.outer;
    payload["holes"] = polygons.holes;
    return payload;
}

}  // namespace

PYBIND11_MODULE(_pwmb_geom, module) {
    module.doc() = "PWMB contour extraction native helpers";
    module.def("extract_polygons", &extract_polygons_py, py::arg("mask"));
}
