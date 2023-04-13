import os
import shutil
import glob
import sys
from io import StringIO
from conan import ConanFile
from conan import tools
from conan.tools.env import Environment
from conan.tools.files import copy, save, load, get, replace_in_file
from conan.tools.gnu import AutotoolsToolchain, AutotoolsDeps
from conan.tools.microsoft import VCVars, is_msvc
from conan.errors import ConanException, ConanInvalidConfiguration


def prepend_file_with(file_path, line):
    lines = []
    with open(file_path) as file:
        lines = file.readlines()

    # Prepend, if we have not already
    if len(lines) > 0 and lines[0] != line:
        lines = [line] + lines

    with open(file_path, "w") as file:
        file.writelines(lines)


def to_cygwin_path(path):
    # Split at drive-separator
    parts = path.split(":\\", 1)
    return "/cygdrive/{0}/{1}".format(parts[0].lower(), parts[1].replace("\\", "/").lower())


def library_suffix(build_type, shared):
    return ("_rt" if shared else "") + ("d.lib" if build_type == "Debug" else ".lib")


class OmniorbConan(ConanFile):
    name = "omniorb"
    version = "4.2.3"
    license = "GNU Lesser General Public License (for the libraries), and GNU General Public License (for the tools)"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "http://omniorb.sourceforge.net/"
    topics = ("corba", "rpc")
    description = "omniORB is a robust high performance CORBA ORB for C++ and Python"
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}
    root = "omniORB-" + version

    def source(self):
        archive_name = "omniORB-{0}.tar.bz2".format(self.version)
        source_url = "https://downloads.sourceforge.net/project/omniorb/omniORB/omniORB-{0}/{1}".format(self.version, archive_name)
        get(self, url=source_url)
        shutil.move("omniORB-{0}".format(self.version), "omniORB")
    
    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
    
    def configure(self):
        if self.options.shared:
            del self.options.fPIC

    def generate(self):
        if not is_msvc(self):
            return
        
        ms = VCVars(self)
        ms.generate()

        # Try to get cygwin from env, or use the default path
        cygwin_bin_path = os.getenv("CYGWIN_BIN_PATH")
        if cygwin_bin_path is None:
            cygwin_bin_path = "C:\\cygwin64\\bin"

        env = Environment()
        env.append_path("PATH", cygwin_bin_path)
        envvars = env.vars(self)
        envvars.save_script("setpath")

    def build_windows(self):
        if not is_msvc(self):
            raise ConanInvalidConfiguration("Can only build using visual studio on windows")

        # Python needs to be the same arch as the target (because omniORB uses the .lib file)
        self.verify_python_arch(sys.executable)

        # 1. set "platform = x86_win32_vs_<VS-version>" in config/config.mk
        omniorb_version = min(int(str(self.settings.compiler.version)), 15)
        platform_name = f"x86_win32_vs_{omniorb_version}"

        config_file_path = os.path.join(self.build_folder, "config/config.mk")
        prepend_file_with(config_file_path, f"platform = {platform_name}\n")
        self.output.info(f"Set platform to {platform_name}")

        # 2. set python in the platform path
        python_cygwin_exe_path = os.path.splitext(to_cygwin_path(sys.executable))[0]
        platform_file_path = os.path.join(self.build_folder, f"mk/platforms/{platform_name}.mk")
        self.output.info(f'Platform file is f{platform_file_path}')
        prepend_file_with(platform_file_path, f"PYTHON = {python_cygwin_exe_path}\n")
        self.output.info(f"Set PYTHON to {python_cygwin_exe_path}")

        # 3. Fix python version detection, so that it works with 2 digit minor versions
        python_mk_path = os.path.join(self.build_folder, "mk/python.mk")
        replace_in_file(self, python_mk_path, search='sys.version[:3]', replace='".".join(sys.version.split(".", 3)[:2])')

        # 4. Set up the right runtime. This is only relevant for static builds, DLLs should always use the DLL runtime
        if not self.options.shared:
            # Static builds default to -MT[d] in the platform file, dynamic to -MD[d]
            runtime = self.settings.compiler.runtime
            old = "MTd" if self.settings.build_type == "Debug" else "MT"
            new = "MT" if runtime == "static" else "MD"
            if self.settings.compiler.runtime_type == "Debug":
                new += "d"

            if old != new:
                replace_in_file(self, platform_file_path, search=f" -{old} ", replace=f" -{new} ")
                self.output.info(f"Changing static runtime flag {old} to {new}")
        elif self.settings.compiler.runtime != "dynamic":
            raise ConanInvalidConfiguration("Need to use dll runtime for dll builds")
        
        # 5. Build!
        src_folder = os.path.join(self.build_folder, "src/")
        self.run('echo %PATH%')
        self.run(f'cd {src_folder}&&make export')

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
        shutil.copytree(source_location, self.build_folder, dirs_exist_ok=True)
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
        return [lib + suffix for lib in base_names]

    def package_windows(self):
        from os.path import join
        copy(self, "*.exe", dst=join(self.package_folder, "bin"), src=join(self.build_folder, "bin"), keep_path=True)
        # Copy only the correct dlls for shared builds
        if self.options.shared:
            pattern = "*_rt.dll" if self.settings.build_type != "Debug" else "*_rtd.dll"
            copy(self, pattern, dst=join(self.package_folder, "bin"),
                 src=join(self.build_folder, "bin"), keep_path=False)
        for lib in self.windows_libraries():
            self.output.info('Packaging library: {0}'.format(lib))
            copy(self, lib, dst=join(self.package_folder, "lib/x86_win32"),
                 src=join(self.build_folder, "lib/x86_win32"), keep_path=True)
        copy(self, "*.h", dst=join(self.package_folder, "include"), src=join(self.build_folder, "include"))
        copy(self, "*.hxx", dst=join(self.package_folder, "include"), src=join(self.build_folder, "include"))
        copy(self, "*.hh", dst=join(self.package_folder, "include"), src=join(self.build_folder, "include"))
        copy(self, "*.py", dst=join(self.package_folder, "lib/python"), src=join(self.build_folder, "lib/python"))
        # Copy license files
        copy(self, "README.FIRST.txt", dst="licenses", src=self.build_folder)
        copy(self, "COPYING", dst="licenses", src=self.build_folder)
        copy(self, "COPYING.LIB", dst="licenses", src=self.build_folder)

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
        self.cpp_info.libs = self.windows_libraries()
        self.cpp_info.system_libs = ["ws2_32.lib", "mswsock.lib", "advapi32.lib"]
        self.cpp_info.libdirs = ["lib/x86_win32"]
        self.cpp_info.defines += ["__WIN32__", "__x86__", "_WIN32_WINNT=0x0400", "__NT__", "__OSVERSION__=4"]
        if not self.options.shared:
            self.cpp_info.defines += ["_WINSTATIC"]
  
    def run_python_script(self, python_exec, script):
        return self.run_command('"%s" -c "%s"' % (python_exec, script))

    def run_command(self, command):
        stream = StringIO()
        self.output.info(f'running {command}')
        try:
            self.run(command=command, stdout=stream, env=None)
        except ConanException as e:
            raise ConanInvalidConfiguration(f"{command} failed: {e})")
        
        output = stream.getvalue().strip()
        self.output.info(output)
        return output if output != "None" else None

    def verify_python_arch(self, python_exec):
        build_arch = self.settings.arch
        correct_arch_for = {'32bit': 'x86', '64bit': 'x86_64'}
        detect_arch = "from __future__ import print_function; import platform; print(platform.architecture()[0])"
        python_arch = self.run_python_script(python_exec, detect_arch)
        actual_arch = correct_arch_for[python_arch]
        if actual_arch != build_arch:
            raise ConanInvalidConfiguration("Incompatible python architecture: python: {0}, but conan build is {1} ({2}).".format(actual_arch, build_arch, python_arch))

