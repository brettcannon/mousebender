# ruff: noqa: ANN001, ANN201, ANN202, D100, D102, D103, D400, D415
import argparse
import dataclasses
import datetime
import io
import operator
import pathlib
import sys
import tomllib

import httpx
import packaging.markers
import packaging.metadata
import packaging.requirements
import packaging.specifiers
import packaging.tags
import packaging.utils
import packaging.version
import resolvelib.resolvers
import trio

import mousebender.resolve
import mousebender.simple


@dataclasses.dataclass
class WheelFile:
    """[[packages.wheels]]"""

    name: str
    url: str
    upload_time: datetime.datetime | None = None
    # path
    size: int | None = None
    hashes: dict[str, str] = dataclasses.field(default_factory=dict)

    def to_toml(self):
        parts = []
        parts.append(f"name = {self.name!r}")
        if self.upload_time:
            parts.append(f"upload-time = {self.upload_time.isoformat()}")
        parts.append(f"url = {self.url!r}")
        if self.size:
            parts.append(f"size = {self.size!r}")
        parts.append(
            f"hashes = {{{', '.join([f'{k} = {v!r}' for k, v in self.hashes.items()])}}}"
        )
        return "".join(["{", ", ".join(parts), "}"])


@dataclasses.dataclass
class PackageVersion:
    """[[packages]]"""

    name: str
    version: packaging.version.Version
    marker: packaging.markers.Marker | None = None
    requires_python: packaging.specifiers.SpecifierSet | None = None
    dependencies: list[packaging.requirements.Requirement] = dataclasses.field(
        default_factory=list
    )
    # vcs
    # directory
    # archive
    index: str | None = None
    # XXX sdist
    wheels: list[WheelFile] = dataclasses.field(default_factory=list)
    # XXX attestation-identities
    tool: dict = dataclasses.field(default_factory=dict)

    def to_toml(self):
        parts = []
        parts.append(f"name = {self.name!r}")
        parts.append(f"version = {str(self.version)!r}")
        if self.marker:
            parts.append(f"marker = {str(self.marker)!r}")
        if self.requires_python:
            parts.append(f"requires-python = {str(self.requires_python)!r}")
        if self.dependencies:
            deps = ["dependencies = ["]
            for dep in self.dependencies:
                deps.append(f"    {{name = {dep.name!r}}},")
            deps.append("]")
            parts.append("\n".join(deps))
        if self.wheels:
            wheels = ["wheels = ["]
            for wheel in self.wheels:
                wheels.append(f"  {wheel.to_toml()},")
            wheels.append("]")
            parts.append("\n".join(wheels))
        if self.tool:
            raise NotImplementedError("[tool] table not implemented")
        return "\n".join(parts)


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
        name = resolved_wheel_file.details["filename"]
        url: str = resolved_wheel_file.details["url"]
        hashes = resolved_wheel_file.details["hashes"]
        if upload_time := resolved_wheel_file.details.get("upload-time"):
            upload_time = datetime.datetime.fromisoformat(upload_time)
        size: int | None = resolved_wheel_file.details.get("size")
        locked_wheel = WheelFile(
            name, url, upload_time=upload_time, size=size, hashes=hashes
        )
        requirements = []
        for req in candidate.file.metadata.requires_dist or []:
            if not req.marker:  # XXX Hack
                requirements.append(req)
        name = candidate.identifier[0]
        version = candidate.file.version
        requires_python = candidate.file.metadata.requires_python
        index = f"https://pypi.org/simple/{name}"  # Hard-coded
        yield PackageVersion(
            name,
            version,
            # XXX markers
            index=index,
            requires_python=requires_python,
            dependencies=requirements,
            wheels=[locked_wheel],
            # XXX attestation_identities
        )


def platform_details(platform):
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

    return markers, list(tags)


def file_lock(markers, tags, dependencies):
    _, resolution = resolve(dependencies, markers, tags)
    return flatten_graph(resolution)


def lock(context):
    dependencies = context.requirements

    locks = {}
    environments = []
    versions = []
    for platform in context.platform or ["system"]:
        markers, tags = platform_details(platform)
        packages = file_lock(markers, tags, dependencies)
        for package in packages:
            key = package.name, package.version
            if key not in locks:
                locks[key] = package
            else:
                for new_wheel in package.wheels:
                    for seen_wheel in locks[key].wheels:
                        if new_wheel.name == seen_wheel.name:
                            break
                        else:
                            locks[key].wheels.append(new_wheel)
        # XXX Hacks upon hacks ...
        first_tag = tags[0]
        interpreter = first_tag.interpreter
        minor_version = int(interpreter.removeprefix("cp3"))
        versions.append((3, minor_version))
        platform = first_tag.platform
        if "manylinux" in platform:
            environments.append("sys_platform == 'linux'")
        elif "win" in platform:
            environments.append("sys_platform == 'win32'")

    buffer = io.StringIO()

    print("lock-version = '1.0'", file=buffer)
    if environments:
        print(f"""environments = ["{'", "'.join(environments)}"]""", file=buffer)
    versions.sort(reverse=True)
    print(f"""requires-python = '==3.{versions[0][1]}'""", file=buffer)
    # XXX extras
    # XXX dependency-groups
    print("created-by = 'mousebender'", file=buffer)
    print(file=buffer)

    for package in sorted(
        locks.values(),
        key=lambda package: (package.name, package.version),
    ):
        print("[[packages]]", file=buffer)
        print(package.to_toml().strip(), file=buffer)
        print(file=buffer)

    # tool

    if context.lock_file:
        with context.lock_file.open("w") as file:
            file.write(buffer.getvalue())
    else:
        print(buffer.getvalue())


def install(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = tomllib.load(file)

    return install_packages(lock_file_contents)


class UnsatisfiableError(Exception):
    """Raised when a requirement cannot be satisfied."""


class AmbiguityError(Exception):
    """Raised when a requirement has multiple solutions."""


def install_packages(lock_file_contents):
    # Hard-coded out of laziness.
    packages = choose_packages(lock_file_contents, (GROUP_NAME, frozenset()))

    for package in packages:
        tags = list(packaging.tags.sys_tags())
        for tag in tags:  # Prioritize by tag order.
            tag_str = str(tag)
            for wheel in package["wheels"]:
                if tag_str in wheel["tags"]:
                    break
            else:
                continue
            break
        else:
            raise UnsatisfiableError(
                f"No wheel for {package['name']} {package['version']}"
            )
        print(f"Installing {package['name']} {package['version']} ({tag_str})")


def choose_packages(lock_file_data, *selected_groups):
    """Select the package versions that should be installed based on the requested groups.

    'selected_groups' is a sequence of two-item tuples, representing a group name and
    optionally any requested extras if the group is a project.
    """
    group_names = frozenset(operator.itemgetter(0)(group) for group in selected_groups)
    available_packages = {}  # The packages in the selected groups.
    for pkg in lock_file_data["packages"]:
        if frozenset(pkg["groups"]) & group_names:
            available_packages.setdefault(pkg["name"], []).append(pkg)
    selected_packages = {}  # The package versions that have been selected.
    handled_extras = {}  # The extras that have been handled.
    requirements = []  # A stack of requirements to satisfy.

    # First, get our starting list of requirements.
    for group in selected_groups:
        requirements.extend(gather_requirements(lock_file_data, group))

    # Next, go through the requirements and try to find a **single** package version
    # that satisfies each requirement.
    while requirements:
        req = requirements.pop()
        # Ignore requirements whose markers disqualify it.
        if not applies_to_env(req):
            continue
        name = req["name"]
        if pkg := selected_packages.get(name):
            # Safety check that the cross-section of groups doesn't cause issues.
            # It somewhat assumes the locker didn't mess up such that there would be
            # ambiguity by what package version was initially selected.
            if not version_satisfies(req, pkg):
                raise UnsatisfiableError(
                    f"requirement {req!r} not satisfied by "
                    f"{selected_packages[req['name']]!r}"
                )
            if "extras" not in req:
                continue
            needed_extras = req["extras"]
            if not (extras := handled_extras.set_default(name, set())).difference(
                needed_extras
            ):
                continue
            # This isn't optimal as we may tread over the same extras multiple times,
            # but eventually the maximum set of extras for the package will be handled
            # and thus the above guard will short-circuit adding any more requirements.
            extras.update(needed_extras)
        else:
            # Raises UnsatisfiableError or AmbiguityError if no suitable, single package
            # version is found.
            pkg = compatible_package_version(req, available_packages[req["name"]])
            selected_packages[name] = pkg
        requirements.extend(dependencies(pkg, req))

    return selected_packages.values()


def gather_requirements(locked_file_data, group):
    """Return a collection of all requirements for a group."""
    # Hard-coded to support `groups.requirements` out of laziness.
    group_name, _extras = group
    for group in locked_file_data["groups"]:
        if group["name"] == group_name:
            return group["requirements"]
    else:
        raise ValueError(f"Group {group_name!r} not found in lock file")


def applies_to_env(requirement):
    """Check if the requirement applies to the current environment."""
    try:
        markers = requirement["marker"]
    except KeyError:
        return True
    else:
        return packaging.markers.Marker(markers).evaluate()


def version_satisfies(requirement, package):
    """Check if the package version satisfies the requirement."""
    try:
        raw_specifier = requirement["version"]
    except KeyError:
        return True
    else:
        specifier = packaging.specifiers.SpecifierSet(raw_specifier)
        return specifier.contains(package["version"], prereleases=True)


def compatible_package_version(requirement, available_packages):
    """Return the package version that satisfies the requirement.

    If no package version can satisfy the requirement, raise UnsatisfiableError. If
    multiple package versions can satisfy the requirement, raise AmbiguityError.
    """
    possible_packages = [
        pkg for pkg in available_packages if version_satisfies(requirement, pkg)
    ]
    if not possible_packages:
        raise UnsatisfiableError(f"No package version satisfies {requirement!r}")
    elif len(possible_packages) > 1:
        raise AmbiguityError(f"Multiple package versions satisfy {requirement!r}")
    return possible_packages[0]


def dependencies(package, requirement):
    """Return the dependencies of the package.

    The extras from the requirement will extend the base requirements as needed.
    """
    applicable_deps = []
    extras = frozenset(requirement.get("extras", []))
    for dep in package["dependencies"]:
        if "feature" not in dep or dep["feature"] in extras:
            applicable_deps.append(dep)
    return applicable_deps


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
            "cpython3.13-manylinux2014-x64",
            "cpython3.8-windows-x64",
            "cpython3.9-windows-x64",
            "cpython3.10-windows-x64",
            "cpython3.11-windows-x64",
            "cpython3.12-windows-x64",
            "cpython3.13-windows-x64",
            "python3.8",
            "python3.9",
            "python3.10",
            "python3.11",
            "python3.12",
            "python3.13",
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
    # py . lock --platform cpython3.12-windows-x64 --platform cpython3.12-manylinux2014-x64 cattrs numpy
