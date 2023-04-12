from conan import ConanFile
from conan.tools.cmake import CMake
import os

class OmniorbTestConan(ConanFile):
    test_type = "explicit"
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps", "CMakeToolchain"
    options = {"shared": [True, False]}
    default_options = "shared=False"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def requirements(self):
        self.requires("omniorb/4.2.3@softwareschneiderei/stable")

    def test(self):
        os.chdir("bin")
        self.run(".%sexample" % os.sep)
