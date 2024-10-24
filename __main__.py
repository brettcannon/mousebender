# ruff: noqa: ANN001, ANN201, ANN202, D100, D102, D103, D400, D415
import argparse
import dataclasses
import datetime
import io
import pathlib
import sys

import httpx
import packaging.markers
import packaging.metadata
import packaging.requirements
import packaging.specifiers
import packaging.utils
import packaging.version
import resolvelib.resolvers
import tomllib
import trio

import mousebender.resolve
import mousebender.simple


@dataclasses.dataclass
class Requirement:
    """[[groups.requirements]], [[packages.dependencies]]"""

    name: packaging.utils.NormalizedName
    extras: frozenset[packaging.utils.NormalizedName] = dataclasses.field(
        default_factory=frozenset
    )
    version: packaging.specifiers.SpecifierSet | None = None
    marker: packaging.markers.Marker | None = None
    feature: str | None = None

    def to_toml(self):
        parts = [f"name = {self.name!r}"]
        if self.extras:
            parts.append(f"extras = {list(self.extras)!r}")
        if self.version:
            parts.append(f"version = {str(self.version)!r}")
        if self.marker:
            parts.append(f"marker = {str(self.marker)!r}")
        # XXX feature
        return f"{{ {", ".join(parts)} }}"


@dataclasses.dataclass
class WheelFile:
    """[[packages.wheels]]"""

    tags: frozenset[str]
    build: str
    url: str
    hash: str
    upload_time: datetime.datetime | None = None
    size: int | None = None

    def to_toml(self):
        tags = list(map(str, self.tags))
        parts = [f"tags = {tags!r}"]
        if self.build:
            parts.append(f"build = {self.build!r}")
        if self.url:
            parts.append(f"url = {self.url!r}")
        parts.append(f"hash = {self.hash!r}")
        if self.upload_time:
            parts.append(f"upload_time = {self.upload_time.isoformat()}")
        if self.size:
            parts.append(f"size = {self.size!r}")
        return f"{{ {", ".join(parts)} }}"


@dataclasses.dataclass
class PackageVersion:
    """[[packages]]"""

    name: str
    version: packaging.version.Version
    groups: list[str] = dataclasses.field(default_factory=list)
    index_url: str = ""
    direct: bool = False
    requires_python: packaging.specifiers.SpecifierSet | None = None
    dependencies: list[Requirement] = dataclasses.field(default_factory=list)
    editable: bool = False
    wheels: list[WheelFile] = dataclasses.field(default_factory=list)

    def to_toml(self):
        return f"""
name = {self.name!r}
version = {str(self.version)!r}
groups = {list(self.groups)!r}
index_url = {self.index_url!r}
direct = {str(self.direct).lower()}
requires_python = {str(self.requires_python)!r}
dependencies = [
  {",\n  ".join(r.to_toml() for r in self.dependencies)}
]
editable = {str(self.editable).lower()}
wheels = [
  {",\n  ".join(w.to_toml() for w in self.wheels)}
]
"""


async def get_metadata_for_file(client, file):
    """Get the METADATA file for a wheel."""
    url = file.details["url"] + ".metadata"
    response = await client.get(url)
    raw_data = response.content
    if isinstance(file.details.get("core-metadata", True), dict):
        pass
    metadata = packaging.metadata.Metadata.from_email(raw_data, validate=False)
    file.metadata = metadata


async def get_metadata(files):
    """Get the METADATA file for a wheel."""
    async with httpx.AsyncClient() as client:
        async with trio.open_nursery() as nursery:
            for file in files:
                nursery.start_soon(get_metadata_for_file, client, file)  # type: ignore[arg-type]


class PyPIProvider(mousebender.resolve.WheelProvider):
    """A provider for wheels from PyPI."""

    def available_files(self, name):
        """Get the available wheels for a distribution."""
        project_url = mousebender.simple.create_project_url(
            "https://pypi.org/simple", name
        )
        response = httpx.get(
            project_url,
            follow_redirects=True,
            headers={"Accept": mousebender.simple.ACCEPT_SUPPORTED},
        )

        project_details = mousebender.simple.parse_project_details(
            response.text, response.headers["Content-Type"], name
        )

        nothing_yanked = list(
            filter(lambda f: not f.get("yanked", False), project_details["files"])
        )

        wheels = list(filter(lambda f: f["filename"].endswith(".whl"), nothing_yanked))
        has_metadata = list(filter(lambda f: f.get("core-metadata", False), wheels))

        if not nothing_yanked:
            print(f"😱 {name} has **no** files available", file=sys.stderr)
        elif not wheels:
            print(f"🤬 {name} has **no** wheels", file=sys.stderr)
        elif not has_metadata:
            print(f"😨 {name} has **no** wheels w/ metadata", file=sys.stderr)
        elif len(has_metadata) < len(wheels):
            print(f"😬 {name} only has **some** wheels w/ metadata", file=sys.stderr)

        return map(mousebender.resolve.WheelFile, has_metadata)

    def fetch_metadata(self, file_details):
        """Fetch the METADATA file for a wheel."""
        trio.run(get_metadata, file_details)


def system_details():
    """Get the details of the current environment."""
    return packaging.markers.default_environment(), packaging.tags.sys_tags()


def pure_python_details(version):
    """Calculate the details for a specific Python version."""
    version_str = f"{version[0]}.{version[1]}"
    markers = {
        "python_version": version_str,
        "python_full_version": f"{version_str}.0",
    }
    # https://github.com/pypa/packaging/issues/781 to get rid of the `filter()`
    # call.
    tags = filter(
        lambda tag: tag.platform != "_",
        packaging.tags.compatible_tags(version, platforms=["_"]),
    )

    return markers, tags


def cpython_windows_details(version):
    version_str = f"{version[0]}.{version[1]}"
    markers = {
        "implementation_name": "cpython",
        "implementation_version": f"{version_str}.0",
        "os_name": "nt",
        "platform_machine": "AMD64",
        "platform_release": "10",
        "platform_system": "Windows",
        "python_full_version": f"{version_str}.0",
        "platform_python_implementation": "CPython",
        "python_version": version_str,
        "sys_platform": "win32",
    }

    tags = [
        *packaging.tags.cpython_tags(
            version, [f"cp{version[0]}{version[1]}", "abi3"], ["win_amd64"]
        ),
        *packaging.tags.compatible_tags(
            version, f"cp{version[0]}{version[1]}", platforms=["win_amd64"]
        ),
    ]

    return markers, tags


def cpython_manylinux_details(version):
    version_str = f"{version[0]}.{version[1]}"
    markers = {
        "implementation_name": "cpython",
        "implementation_version": f"{version_str}.0",
        "os_name": "posix",
        "platform_machine": "x86_64",
        "platform_system": "Linux",
        "python_full_version": f"{version_str}.0",
        "platform_python_implementation": "CPython",
        "python_version": version_str,
        "sys_platform": "linux",
    }

    # manylinux 2014 and older.
    platforms = [f"manylinux_2_{minor}_x86_64" for minor in range(17, 4, -1)]
    tags = [
        *packaging.tags.cpython_tags(
            version, [f"cp{version[0]}{version[1]}", "abi3"], platforms
        ),
        *packaging.tags.compatible_tags(
            version, f"cp{version[0]}{version[1]}", platforms=platforms
        ),
    ]

    return markers, tags


def resolve(dependencies, markers, tags):
    pkg_requirements = map(packaging.requirements.Requirement, dependencies)
    requirements = list(
        map(
            mousebender.resolve.Requirement,
            filter(
                lambda r: r.marker is None or r.marker.evaluate(markers),
                pkg_requirements,
            ),
        )
    )
    provider = PyPIProvider(markers=markers, tags=tags)
    reporter = resolvelib.BaseReporter()
    resolver: resolvelib.Resolver = resolvelib.Resolver(provider, reporter)
    try:
        resolution = resolver.resolve(requirements)
    except resolvelib.ResolutionImpossible:
        print("Resolution (currently) impossible 😢")
        sys.exit(1)

    return provider, resolution


def flatten_graph(resolution):
    """Take the dependency graph and return the collection of nodes/packages."""
    # for id_ in resolution.graph.iter_children(None):
    for candidate in resolution.mapping.values():
        # candidate = resolution.mapping[id_]
        resolved_wheel_file = candidate.file
        tags = resolved_wheel_file.wheel.tags
        build_tag = resolved_wheel_file.wheel.build_tag
        url: str = resolved_wheel_file.details["url"]
        hash_: str = resolved_wheel_file.details["hashes"]["sha256"]
        if upload_time := resolved_wheel_file.details.get("upload-time"):
            upload_time = datetime.datetime.fromisoformat(upload_time)
        size: int | None = resolved_wheel_file.details.get("size")
        locked_wheel = WheelFile(tags, build_tag, url, hash_, upload_time, size)
        # requirement
        requirements = []
        for req in candidate.file.metadata.requires_dist or []:
            name = packaging.utils.canonicalize_name(req.name)
            extras = frozenset(map(packaging.utils.canonicalize_name, req.extras))
            version = req.specifier
            marker = req.marker
            # XXX feature
            requirements.append(Requirement(name, extras, version, marker))
        name = candidate.identifier[0]
        version = candidate.file.version
        groups = ["Default"]  # Hard-coded
        index_url = f"https://pypi.org/simple/{name}"  # Hard-coded
        direct = False  # Hard-coded
        requires_python = candidate.file.metadata.requires_python
        editable = False  # Hard-coded
        yield PackageVersion(
            name,
            version,
            groups,
            index_url,
            direct,
            requires_python,
            requirements,
            editable,
            [locked_wheel],
        )


def file_lock(platform, dependencies):
    if platform == "system":
        markers, tags = system_details()
    elif platform.startswith("python"):
        markers, tags = pure_python_details(
            tuple(map(int, platform.removeprefix("python").split(".", 1)))
        )
    elif platform.startswith("cpython") and platform.endswith("windows-x64"):
        version = platform.removeprefix("cpython").removesuffix("-windows-x64")
        markers, tags = cpython_windows_details(tuple(map(int, version.split(".", 1))))
    elif platform.startswith("cpython") and platform.endswith("-manylinux2014-x64"):
        version = platform.removeprefix("cpython").removesuffix("-manylinux2014-x64")
        markers, tags = cpython_manylinux_details(
            tuple(map(int, version.split(".", 1)))
        )
    else:
        raise ValueError(f"Unknown platform: {platform}")
    tags = list(tags)
    _, resolution = resolve(dependencies, markers, tags)
    return flatten_graph(resolution)


def lock(context):
    dependencies = context.requirements

    locks = {}
    for platform in context.platform or ["system"]:
        packages = file_lock(platform, dependencies)
        for package in packages:
            key = package.name, package.version
            if key not in locks:
                locks[key] = package
            else:
                for new_wheel in package.wheels:
                    found = False
                    for seen_wheel in locks[key].wheels:
                        if new_wheel.tags == seen_wheel.tags:
                            found = True
                            break
                    else:
                        locks[key].wheels.append(new_wheel)

    buffer = io.StringIO()

    print("version = '1.0'", file=buffer)
    print("hash-algorithm = 'sha256'", file=buffer)
    print(file=buffer)

    print("[locker]", file=buffer)
    print("name = 'mousebender'", file=buffer)
    print("version = 'pep'", file=buffer)
    print(f"run = {{ module = 'mousebender', args = {sys.argv[1:]!r} }}", file=buffer)
    print(file=buffer)

    for package in sorted(
        locks.values(),
        key=lambda package: (package.name, package.version),
    ):
        print("[[packages]]", file=buffer)
        print(package.to_toml().strip(), file=buffer)
        print(file=buffer)

    if context.lock_file:
        with context.lock_file.open("w") as file:
            file.write(buffer.getvalue())
    else:
        print(buffer.getvalue())


def find_packages(lock_file_contents):
    # XXX install
    raise NotImplementedError


def install(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = tomllib.load(file)

    files = find_packages(lock_file_contents)[2]

    for file in files:
        print(file["name"])


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="subcommand")

    lock_args = subcommands.add_parser("lock", help="Generate a lock file")
    lock_args.add_argument("requirements", nargs="*")
    lock_args.add_argument(
        "--lock-file", type=pathlib.Path, help="Where to save the lock file"
    )

    lock_args.add_argument(
        "--platform",
        action="append",
        choices=[
            "system",
            "cpython3.8-manylinux2014-x64",
            "cpython3.9-manylinux2014-x64",
            "cpython3.10-manylinux2014-x64",
            "cpython3.11-manylinux2014-x64",
            "cpython3.12-manylinux2014-x64",
            "cpython3.8-windows-x64",
            "cpython3.9-windows-x64",
            "cpython3.10-windows-x64",
            "cpython3.11-windows-x64",
            "cpython3.12-windows-x64",
            "python3.8",
            "python3.9",
            "python3.10",
            "python3.11",
            "python3.12",
        ],
        default=[],
        help="The platform to lock for",
    )

    install_args = subcommands.add_parser(
        "install", help="Install packages from a lock file"
    )
    install_args.add_argument(
        "lock_file", type=pathlib.Path, help="The lock file to install from"
    )

    context = parser.parse_args(args)
    dispatch = {
        "lock": lock,
        "install": install,
    }
    dispatch[context.subcommand](context)


if __name__ == "__main__":
    main()
    # py . lock numpy mousebender hatchling requests pydantic
    # trio
