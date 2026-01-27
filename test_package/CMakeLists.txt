cmake_minimum_required(VERSION 3.15)
project(OmniorbPackageTest CXX)

find_package(omniORB4 CONFIG REQUIRED)

add_executable(example example.cpp)
target_link_libraries(example PUBLIC omniORB4::omniORB4)
