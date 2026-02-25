#pragma once

#include <array>
#include <vector>

namespace pwmb_geom {

using Point2d = std::array<double, 2>;
using Loop2d = std::vector<Point2d>;
using Triangle2d = std::array<Point2d, 3>;

std::vector<Triangle2d> triangulate_polygon_with_holes(
    const Loop2d& outer,
    const std::vector<Loop2d>& holes);

}  // namespace pwmb_geom
