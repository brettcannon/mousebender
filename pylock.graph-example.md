```mermaid
graph LR
  subgraph top [Top-level dependencies]
    hatchling
    mousebender
    numpy
    pydantic
    requests
  end
  subgraph cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64
    annotated-types
    certifi
    charset-normalizer
    editables
    hatchling
    packaging
    pathspec
    pluggy
    trove-classifiers
    idna
    mousebender
    typing-extensions
    numpy
    pydantic
    pydantic-core
    requests
    urllib3
    hatchling --> editables
    hatchling --> packaging
    hatchling --> pathspec
    hatchling --> pluggy
    hatchling --> trove-classifiers
    mousebender --> packaging
    mousebender --> typing-extensions
    pydantic --> annotated-types
    pydantic --> pydantic-core
    pydantic --> typing-extensions
    pydantic-core --> typing-extensions
    requests --> certifi
    requests --> charset-normalizer
    requests --> idna
    requests --> urllib3
  end
```
