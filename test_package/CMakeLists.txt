cmake_minimum_required(VERSION 3.15)
project(OmniorbPackageTest CXX)

find_package(omniorb CONFIG REQUIRED)

add_executable(example example.cpp)
target_link_libraries(example PUBLIC omniorb::omniorb)
