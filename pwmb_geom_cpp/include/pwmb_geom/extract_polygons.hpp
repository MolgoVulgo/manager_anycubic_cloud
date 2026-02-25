#pragma once

#include <array>
#include <cstdint>
#include <vector>

namespace pwmb_geom {

using Point2i = std::array<int, 2>;
using Loop2i = std::vector<Point2i>;

struct PolygonSet {
    std::vector<Loop2i> outer;
    std::vector<Loop2i> holes;
};

enum class ContourImpl {
    kNative,
    kOpenCV,
};

PolygonSet extract_polygons(
    const std::uint8_t* data,
    int width,
    int height,
    ContourImpl impl = ContourImpl::kNative);

bool opencv_contours_available() noexcept;

}  // namespace pwmb_geom
