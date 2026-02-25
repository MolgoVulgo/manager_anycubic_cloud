from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from pwmb_core import read_pwmb_document
from render3d_core.backend import PythonGeometryBackend
from render3d_core.invariants import build_invariant_snapshot
from render3d_core.pipeline import build_geometry_pipeline


def _md5_vertices(vertices: object) -> str:
    arr = np.asarray(vertices, dtype=np.float32)
    return hashlib.md5(arr.tobytes()).hexdigest()


def _load_cube_golden() -> dict[str, object]:
    golden_path = Path("tests/goldens/render3d_cube_golden.json")
    return json.loads(golden_path.read_text(encoding="utf-8"))


def test_cube_pwmb_non_regression_golden_orientation_bbox_checksum() -> None:
    golden = _load_cube_golden()
    sample_path = Path(str(golden["file"]))
    if not sample_path.exists():
        pytest.skip(f"Missing golden sample: {sample_path}")

    params = dict(golden["params"])
    document = read_pwmb_document(sample_path)
    result = build_geometry_pipeline(
        document,
        threshold=int(params["threshold"]),
        bin_mode=str(params["bin_mode"]),
        xy_stride=int(params["xy_stride"]),
        z_stride=int(params["z_stride"]),
        include_fill=bool(params["include_fill"]),
        max_xy_stride=1,
        backend=PythonGeometryBackend(),
        cache=None,
    )
    snapshot = build_invariant_snapshot(result.contour_stack, result.geometry).as_dict()
    expected_inv = golden["invariants"]
    expected_checksums = golden["checksums"]

    assert snapshot["triangle_count"] == expected_inv["triangle_count"]
    assert snapshot["degenerate_triangles"] == expected_inv["degenerate_triangles"]
    assert snapshot["contour_area_mm2"] == pytest.approx(expected_inv["contour_area_mm2"], rel=1e-6, abs=1e-4)
    assert snapshot["mesh_area_mm2"] == pytest.approx(expected_inv["mesh_area_mm2"], rel=1e-6, abs=1e-4)

    contour_bbox = snapshot["contour_bbox"]
    mesh_bbox = snapshot["mesh_bbox"]
    assert contour_bbox is not None
    assert mesh_bbox is not None
    assert tuple(contour_bbox) == pytest.approx(tuple(expected_inv["contour_bbox"]), rel=1e-6, abs=1e-4)
    assert tuple(mesh_bbox) == pytest.approx(tuple(expected_inv["mesh_bbox"]), rel=1e-6, abs=1e-4)

    tri_md5 = _md5_vertices(result.geometry.triangle_vertices)
    line_md5 = _md5_vertices(result.geometry.line_vertices)
    point_md5 = _md5_vertices(result.geometry.point_vertices)
    assert tri_md5 == expected_checksums["tri_md5"]
    assert line_md5 == expected_checksums["line_md5"]
    assert point_md5 == expected_checksums["point_md5"]
