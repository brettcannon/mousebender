# ruff: noqa: ANN001, ANN201, ANN202, D100, D103, D400, D415
import argparse
import dataclasses
import pathlib
import sys
import textwrap

import httpx
import packaging.metadata
import packaging.requirements
import packaging.utils
import resolvelib.resolvers
import tomllib
import trio

import mousebender.install
import mousebender.lock
import mousebender.resolve
import mousebender.simple


# https://github.com/brettcannon/peps/blob/lock-file/peps/pep-9999.rst
@dataclasses.dataclass
class File:
    """[[package.file]]"""

    name: str
    hash: str
    # simple_repo_package_url
    origin: str | None = None
    lock: list[str] = dataclasses.field(default_factory=list)

    def to_toml(self):
        return f"{{name = {self.name!r}, lock = {sorted(self.lock)!r}, origin = {self.origin!r}, hash = {self.hash!r}}}"


@dataclasses.dataclass
class PackageVersion:
    """[[package]]"""

    name: str
    version: str
    # multiple_entries
    files: list[File] = dataclasses.field(default_factory=list)
    description: str | None = None
    simple_repo_package_url: str | None = None
    # marker
    requires_python: str | None = None
    dependents: list[str] | None = None
    dependencies: list[str] | None = None
    direct: bool = False

    def to_toml(self):
        return textwrap.dedent(f"""
            name = {self.name!r}
            version = {self.version!r}
            description = {self.description!r}
            requires-python = {self.requires_python!r}
            dependents = {self.dependents!r}
            dependencies = {self.dependencies!r}
            direct = {str(self.direct).lower()}
            file = [
                {",\n".join(file.to_toml() for file in self.files)}
            ]
        """)


async def get_metadata_for_file(client, file):
    """Get the METADATA file for a wheel."""
    url = file.details["url"] + ".metadata"
    response = await client.get(url)
    raw_data = response.content
    if isinstance(file.details.get("core-metadata", True), dict):
        # TODO If core-metadata is a dict, verify the hash of the data
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
            print(f"😬 {name} has *some* wheels w/o metadata", file=sys.stderr)

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


def calc_dependencies(resolution):
    dependencies = {}  # type: ignore
    seen = set()
    queue = list(resolution.graph.iter_children(None))
    for distro in queue:
        if distro in seen:
            continue
        seen.add(distro)
        children = dependencies.setdefault(
            distro, {"parents": set(), "children": set()}
        )["children"]
        for child in resolution.graph.iter_children(distro):
            children.add(child)
            parents = dependencies.setdefault(
                child, {"parents": set(), "children": set()}
            )["parents"]
            parents.add(distro)
            queue.append(child)

    return dependencies


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


def process_lock(provider, resolution, dependencies):
    packages = []
    for id_ in sorted(dependencies):
        candidate = resolution.mapping[id_]
        wheel = candidate.file
        name = wheel.name
        version = str(wheel.version)
        metadata = wheel.metadata
        file_details = wheel.details
        wheel_file = File(
            file_details["filename"],
            file_details["hashes"]["sha256"],
            origin=file_details["url"],
        )
        package = PackageVersion(name, version)
        package.description = metadata.summary
        # Hard-coded
        package.simple_repo_package_url = f"https://pypi.org/project/{name}/"
        package.requires_python = str(metadata.requires_python)
        package.dependencies = sorted(dep[0] for dep in dependencies[id_]["children"])
        package.dependents = sorted(dep[0] for dep in dependencies[id_]["parents"])
        package.files.append(wheel_file)

        packages.append(package)

    return packages


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
    provider, resolution = resolve(dependencies, markers, tags)
    dependencies = calc_dependencies(resolution)
    packages = process_lock(provider, resolution, dependencies)
    return str(tags[0]), packages


def lock(context):
    if not (dependencies := context.requirements):
        with open("pyproject.toml", "rb") as file:
            pyproject = tomllib.load(file)
        dependencies = pyproject["project"]["dependencies"]

    locks = {}
    for platform in context.platform:
        top_tag, packages = file_lock(platform, dependencies)
        for package in packages:
            package.files[0].lock.append(top_tag)
        locks[top_tag] = packages

    for package in packages:
        print("[[package]]")
        print(package.to_toml().strip())
        print()

    # XXX create a lock file


def install(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = mousebender.lock.parse(file.read())
    if (lock_entry := mousebender.install.strict_match(lock_file_contents)) is None:
        lock_entry = mousebender.install.compatible_match(lock_file_contents)
        if lock_entry is None:
            print("No compatible lock entry found 😢")
            sys.exit(1)

    for wheel in lock_entry["wheel"]:
        print(wheel["name"], "@", wheel.get("filename") or wheel["origin"])


def graph(context):
    with context.lock_file.open("rb") as file:
        lock_file_contents = mousebender.lock.parse(file.read())

    mermaid_lines = []
    if context.self_contained:
        mermaid_lines.append("```mermaid")
    mermaid_lines.extend(["graph LR", "  subgraph top [Top-level dependencies]"])

    for top_dep in lock_file_contents["dependencies"]:
        requirement = packaging.requirements.Requirement(top_dep)
        line = f"    {requirement.name}"
        if requirement.name != top_dep:
            line += f"[{top_dep}]"
        mermaid_lines.append(line)
    mermaid_lines.append("  end")

    for entry in lock_file_contents["lock"]:
        nodes = set()
        edges = {}  # type: ignore
        mermaid_lines.append(f"  subgraph {entry['tags'][0]}")
        for wheel in entry["wheel"]:
            name = wheel["name"]
            if name not in nodes:
                mermaid_lines.append(f"    {name}")
                nodes.add(name)
            for dep in wheel["dependencies"]:
                if dep not in nodes:
                    mermaid_lines.append(f"    {dep}")
                    nodes.add(dep)
                edges.setdefault(name, set()).add(dep)

        for parent, children in edges.items():
            for child in sorted(children):
                mermaid_lines.append(f"    {parent} --> {child}")
        mermaid_lines.append("  end")

    if context.self_contained:
        mermaid_lines.append("```")

    print("\n".join(mermaid_lines))


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
        default=["system"],
        help="The platform to lock for",
    )

    install_args = subcommands.add_parser(
        "install", help="Install packages from a lock file"
    )
    install_args.add_argument(
        "lock_file", type=pathlib.Path, help="The lock file to install from"
    )

    graph_args = subcommands.add_parser(
        "graph",
        help="Generate a visualization of the dependency graph in Mermaid format",
    )
    graph_args.add_argument(
        "--self-contained",
        action="store_true",
        default=False,
        help="Include the surrounding Markdown to make the graph self-contained",
    )
    graph_args.add_argument(
        "lock_file", type=pathlib.Path, help="The lock file to visualize"
    )

    context = parser.parse_args(args)
    dispatch = {
        "lock": lock,
        "install": install,
        "graph": graph,
    }
    dispatch[context.subcommand](context)


if __name__ == "__main__":
    main()
    # py . lock numpy mousebender hatchling requests pydantic
    # trio
