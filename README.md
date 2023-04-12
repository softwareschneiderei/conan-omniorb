[![Build status](https://ci.appveyor.com/api/projects/status/b444lhqmnt3fdrn5?svg=true)](https://ci.appveyor.com/project/softwareschneiderei/conan-omniorb)

# conan-omniorb

[Conan.io](https://conan.io) package for [omniORB](http://omniorb.sourceforge.net) library

Currently there are no generated packages available.

## Build packages

Download conan client from [Conan.io](https://conan.io) and run:

    $ conan create .

### Windows

Python needs to be available in the PATH for building.
Depending on the conan "arch" setting, you will require a different python architecture as well:
 * x86: 32-bit version of python
 * x86-64: 64-bit version of python

Cygwin needs to be installed as well with the standard tools which should be installed by default
and GNU make from the devel category. The recipe will look for the cygwin binaries in C:\cygwin64\bin,
by default. If you used another location, use the environment variable CYGWIN_BIN_PATH to point to your
bin/ folder.