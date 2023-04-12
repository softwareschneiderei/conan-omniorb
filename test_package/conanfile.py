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
        # Currently does not work because VS builds to a release folder
        #os.chdir("bin")
        #self.run(".%sexample" % os.sep)
        pass
