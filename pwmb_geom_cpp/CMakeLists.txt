cmake_minimum_required(VERSION 3.20)
project(pwmb_geom_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
option(WITH_OPENCV "Enable OpenCV contours implementation" OFF)
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m pybind11 --cmakedir
    RESULT_VARIABLE PYBIND11_CMAKEDIR_STATUS
    OUTPUT_VARIABLE PYBIND11_CMAKEDIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)
if(PYBIND11_CMAKEDIR_STATUS EQUAL 0 AND EXISTS "${PYBIND11_CMAKEDIR}")
    list(PREPEND CMAKE_PREFIX_PATH "${PYBIND11_CMAKEDIR}")
endif()

find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(
    _pwmb_geom
    MODULE
    src/module.cpp
    src/extract_polygons.cpp
    src/triangulate.cpp
)
target_include_directories(_pwmb_geom PRIVATE include)
if(WITH_OPENCV)
    find_package(OpenCV QUIET COMPONENTS core imgproc)
    if(NOT OpenCV_FOUND)
        message(FATAL_ERROR "WITH_OPENCV=ON but OpenCV (core,imgproc) was not found")
    endif()
    target_include_directories(_pwmb_geom PRIVATE ${OpenCV_INCLUDE_DIRS})
    target_link_libraries(_pwmb_geom PRIVATE ${OpenCV_LIBS})
    target_compile_definitions(_pwmb_geom PRIVATE PWMB_GEOM_WITH_OPENCV=1)
endif()

set_target_properties(
    _pwmb_geom
    PROPERTIES
    OUTPUT_NAME "_pwmb_geom"
)

install(TARGETS _pwmb_geom LIBRARY DESTINATION pwmb_geom)
