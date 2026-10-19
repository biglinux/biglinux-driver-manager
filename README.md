# pkgbuild-template

Package description

---

## Using this template

This repository is a GitHub template for new BigLinux packages. Click
**Use this template → Create a new repository**, choose the `biglinux`
organization and name the repository after the package (the name becomes the
`pkgname`). Then:

1. Edit `pkgbuild/PKGBUILD`:
   - set `pkgname` to the repository name and write the `pkgdesc`;
   - fill in the maintainer line and uncomment `depends`, `makedepends`… as needed;
   - `pkgver` and `pkgrel` come from the build date, so every build is a new version.
2. Put the files to install in `usr/`, `etc/` or `opt/` at the root of the
   repository, with the same layout they have on the system
   (for example `usr/bin/my-tool`). `package()` copies those folders as they are.
3. If the package needs to run something when it is installed, upgraded or
   removed, edit `pkgbuild/pkgbuild.install`: uncomment the functions you need
   and replace `PACKAGE_NAME` with the package name. If not, delete the file.
4. Replace this section with the package description.

### Building and publishing

Build the package with [gitrepo](https://github.com/big-comm/gitrepo), choosing
**BigLinux** as the destination and the `testing` or `stable` repository. The
[biglinux/build-package](https://github.com/biglinux/build-package) robot
builds, signs and publishes it in
[packages.biglinux.com.br](https://packages.biglinux.com.br).

To test locally:

```bash
cd pkgbuild && makepkg -si
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
