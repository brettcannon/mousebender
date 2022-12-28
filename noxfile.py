"""Developer-related actions.

All sessions prefixed with `check_` are non-destructive.

"""
import nox

python_versions = ["3.7", "3.8", "3.9", "3.10", "3.11"]


@nox.session(python=python_versions)
def test(session, coverage=False):
    """Run the test suite."""
    session.install("-e", ".[test]")
    session.run(
        "pytest", *(["--cov", "--cov-report", "term-missing"] if coverage else [])
    )


@nox.session(python=python_versions)
def coverage(session):
    """Run the test suite under coverage."""
    test(session, coverage=True)


@nox.session
def check_types(session):
    """Type check."""
    session.install("-e", ".[test]")
    session.install("mypy")
    session.run("mypy", "mousebender", "tests")


@nox.session
def format(session, check=False):
    """Format the code."""
    tool = "black"
    session.install(tool)
    args = ["--check"] if check else []
    args.append(".")
    session.run(tool, *args)


@nox.session
def check_format(session):
    """Check that the code is properly formatted."""
    format(session, check=True)


@nox.session
def check_code(session):
    """Lint the code."""
    session.install("ruff>=0.0.132")
    session.run("ruff", "mousebender", "tests")


@nox.session
def docs(session):
    """Build the documentation."""
    session.install("-e", ".[doc]")
    session.run("sphinx-build", "-W", "--keep-going", "docs", "docs/_build")


@nox.session
def build(session):
    """Build the wheel and sdist."""
    session.install("flit")
    session.run("flit", "build")
