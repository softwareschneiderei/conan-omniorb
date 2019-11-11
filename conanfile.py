import os
import shutil
import glob
from conans import ConanFile, tools, AutoToolsBuildEnvironment

class OmniorbConan(ConanFile):
    name = "omniorb"
    version = "4.2.2"
    license = "GNU Lesser General Public License (for the libraries), and GNU General Public License (for the tools)"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "omniORB is a robust high performance CORBA ORB for C++ and Python"
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False]}
    default_options = "shared=False"
    generators = "cmake"
    root = "omniORB-" + version

    def source(self):
        archive_name = "omniORB-{0}.tar.bz2".format(self.version)
        source_url = "https://downloads.sourceforge.net/project/omniorb/omniORB/omniORB-{0}/{1}".format(self.version, archive_name)
        tools.get(source_url)
        shutil.move("omniORB-{0}".format(self.version), "omniORB")

    def build(self):
        source_location = os.path.join(self.build_folder, "omniORB")
        autotools = AutoToolsBuildEnvironment(self)
        args = [
            "--disable-static" if self.options.shared else "--enable-static",
        ]
        autotools.configure(configure_dir=source_location, args=args)
        autotools.make()

    def package(self):
        autotools = AutoToolsBuildEnvironment(self)
        autotools.install()
        # Delete all shared-objects for static-mode, since we cannot prevent building them
        if not self.options.shared:
            for shared_object in glob.iglob(os.path.join(self.package_folder, "lib", "lib*.so*")):
                os.remove(shared_object)

    def package_info(self):
        self.cpp_info.libs = ['omniORB4','omnithread', "omniDynamic4", "COS4"]
        if not self.options.shared:
            self.cpp_info.libs += ['pthread']

