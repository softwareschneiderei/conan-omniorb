import os
from conan import ConanFile
from conan.tools.cmake import CMake


class OmniorbTestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps", "CMakeToolchain"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        os.chdir(self.cpp.build.bindir)
        self.run(".%sexample" % os.sep)
        pass
