{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.setuptools
    pkgs.gcc
    pkgs.libffi
    pkgs.openssl
    pkgs.zlib
    pkgs.libjpeg
    pkgs.freetype
    pkgs.lcms2
    pkgs.libwebp
    pkgs.tcl
    pkgs.tk
  ];
}
