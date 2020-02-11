import os
import shutil
import glob
try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO
from conans import ConanFile, tools, AutoToolsBuildEnvironment
from conans.errors import ConanException, ConanInvalidConfiguration


def prepend_file_with(file_path, line):
    lines = []
    with open(file_path) as file:
        lines = file.readlines()

    # Prepend, if we have not already
    if len(lines) > 0 and lines[0] != line:
        lines = [line] + lines

    with open(file_path, "w") as file:
        file.writelines(lines)


def convert_to_cygwin(path):
    # Split at drive-separator
    parts = path.split(":\\", 1)
    return "/cygdrive/{0}/{1}".format(parts[0].lower(), parts[1].replace("\\", "/").lower())


def library_suffix(build_type, shared):
    return "_rt" if shared else "" + "d.lib" if build_type == "Debug" else ".lib"


# From https://stackoverflow.com/questions/1868714/how-do-i-copy-an-entire-directory-of-files-into-an-existing-directory-using-pyth/31039095
def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)



class OmniorbConan(ConanFile):
    name = "omniorb"
    version = "4.2.3"
    license = "GNU Lesser General Public License (for the libraries), and GNU General Public License (for the tools)"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "omniORB is a robust high performance CORBA ORB for C++ and Python"
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False]}
    default_options = "shared=False"
    generators = ["cmake", "txt"]
    root = "omniORB-" + version

    def source(self):
        archive_name = "omniORB-{0}.tar.bz2".format(self.version)
        source_url = "https://downloads.sourceforge.net/project/omniorb/omniORB/omniORB-{0}/{1}".format(self.version, archive_name)
        tools.get(source_url)
        shutil.move("omniORB-{0}".format(self.version), "omniORB")

    def build_requirements(self):
        if self.settings.os == "Windows":
            self.build_requires("python_dev_config/0.6@bincrafters/stable")
            self.build_requires("cygwin_installer/2.9.0@bincrafters/stable")
        
    def build_windows(self):
        if self.settings.compiler != "Visual Studio":
            raise ConanInvalidConfiguration("Can only build using visual studio on windows")
        
        # Python needs to be the same arch as the target (because omniORB uses the .lib file)
        try:
            python_exe_path = self.deps_user_info["python_dev_config"].python_exec
        except KeyError:
            raise ConanException("Unable to resolve python executable. Make sure that PATH contains a python installation matching your arch setting, i.e. the path to the executable and the Scripts/ folder")
            
        self.verify_python_arch(python_exe_path)

        # 1. set "platform = x86_win32_vs_<VS-version>" in config/config.mk
        omniorb_version = min(int(str(self.settings.compiler.version)), 15)
        platform_name = "x86_win32_vs_{0}".format(omniorb_version)

        config_file_path = os.path.join(self.build_folder, "config/config.mk")
        prepend_file_with(config_file_path, "platform = {0}\n".format(platform_name))
        self.output.info("Set platform to {0}".format(platform_name))

        # 2. set python in the platform path
        python_cygwin_exe_path = os.path.splitext(convert_to_cygwin(python_exe_path))[0]
        platform_file_path = os.path.join(self.build_folder, "mk/platforms/{0}.mk".format(platform_name))
        prepend_file_with(platform_file_path, "PYTHON = {0}\n".format(python_cygwin_exe_path))
        self.output.info("Set PYTHON to {0}".format(python_cygwin_exe_path))

        # 3. Setup the right runtime (which is only relevant for static builds - dlls should always use the dll runtime)
        if not self.options.shared:
            runtime = self.settings.compiler.runtime
            old = " -MTd " if self.settings.build_type == "Debug" else " -MT "
            tools.replace_in_file(platform_file_path, old, " -{0} ".format(runtime))
            self.output.info("Set static runtime to {0}".format(runtime))

        with tools.vcvars(self.settings):
            self.run('cd src/ && make export', win_bash=True)

    def build_linux(self):
        autotools = AutoToolsBuildEnvironment(self)
        args = [
            "--disable-static" if self.options.shared else "--enable-static",
        ]
        autotools.configure(configure_dir=self.build_folder, args=args)
        autotools.make()

    def build(self):
        source_location = os.path.join(self.source_folder, "omniORB")
        self.output.info("source {0}, build {1}".format(source_location, self.build_folder))
        copytree(source_location, self.build_folder)
        if self.settings.os == "Windows":
            self.build_windows()
        elif self.settings.os == "Linux":
            self.build_linux()
        else:
            raise ConanInvalidConfiguration("Unsupported OS")

    def package(self):
        if self.settings.os == "Windows":
            self.package_windows()
        elif self.settings.os == "Linux":
            self.package_linux()
        else:
            raise ConanInvalidConfiguration("Unsupported OS")

    def windows_libraries(self):
        base_names = ['COS4', 'COSDynamic4', 'omniCodeSets4', 'omniDynamic4', 'omniORB4', 'omnithread']
        suffix = library_suffix(self.settings.build_type, self.options.shared)
        return (lib + suffix for lib in base_names)

    def package_windows(self):
        self.copy("*.exe", dst="bin", src=os.path.join(self.build_folder, "bin"), keep_path=True)
        for lib in self.windows_libraries():
            self.copy(lib, dst="lib/x86_win32", src=os.path.join(self.build_folder, "lib/x86_win32"), keep_path=True)
        self.copy("*.h", dst="include", src="include")
        self.copy("*.hxx", dst="include", src="include")
        self.copy("*.hh", dst="include", src="include")
        self.copy("*.py", dst="lib/python", src="lib/python")

    def package_linux(self):
        autotools = AutoToolsBuildEnvironment(self)
        autotools.install()
        # Delete all shared-objects for static-mode, since we cannot prevent building them
        if not self.options.shared:
            for shared_object in glob.iglob(os.path.join(self.package_folder, "lib", "lib*.so*")):
                os.remove(shared_object)

    def package_info(self):
        if self.settings.os == "Windows":
            self.package_info_windows()
        elif self.settings.os == "Linux":
            self.package_info_linux()
        else:
            raise ConanInvalidConfiguration("Unsupported OS")

    def package_info_linux(self):
        self.cpp_info.libs = ['omniDynamic4', 'COS4', 'omniORB4','omnithread',]
        if not self.options.shared:
            self.cpp_info.libs += ['pthread']

    def package_info_windows(self):
        self.cpp_info.libs = [x for x in self.windows_libraries()] + ["ws2_32.lib", "mswsock.lib", "advapi32.lib"]
        self.cpp_info.libdirs = ["lib/x86_win32"]
        self.cpp_info.defines += ["__WIN32__", "__x86__", "_WIN32_WINNT=0x0400", "__NT__", "__OSVERSION__=4"]
        if not self.options.shared:
            self.cpp_info.defines += ["_WINSTATIC"]
  
    def run_python_script(self, python_exec, script):
        output = StringIO()
        command = '"%s" -c "%s"' % (python_exec, script)
        self.output.info('running %s' % command)
        try:
            self.run(command=command, output=output)
        except ConanException:
            self.output.info("(failed)")
            return None
        output = output.getvalue().strip()
        self.output.info(output)
        return output if output != "None" else None

    def verify_python_arch(self, python_exec):
        build_arch = self.settings.arch
        correct_arch_for = { '32bit': 'x86', '64bit': 'x86_64' }
        detect_arch = "from __future__ import print_function; import platform; print(platform.architecture()[0])"
        python_arch = self.run_python_script(python_exec, detect_arch)
        actual_arch = correct_arch_for[python_arch]
        if actual_arch != build_arch:
            raise ConanInvalidConfiguration("Incompatible python architecture: python: {0}, but conan build is {1} ({2}).".format(actual_arch, build_arch, python_arch))

