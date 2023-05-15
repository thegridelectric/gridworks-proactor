# Gridworks Proactor

[![PyPI](https://img.shields.io/pypi/v/gridworks-proactor.svg)][pypi status]
[![Status](https://img.shields.io/pypi/status/gridworks-proactor.svg)][pypi status]
[![Python Version](https://img.shields.io/pypi/pyversions/gridworks-proactor)][pypi status]
[![License](https://img.shields.io/pypi/l/gridworks-proactor)][license]

[![Read the documentation at https://gridworks-proactor.readthedocs.io/](https://img.shields.io/readthedocs/gridworks-proactor/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/thegridelectric/gridworks-proactor/workflows/Tests/badge.svg)][tests]
[![Codecov](https://codecov.io/gh/thegridelectric/gridworks-proactor/branch/main/graph/badge.svg)][codecov]

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)][black]

[pypi status]: https://pypi.org/project/gridworks-proactor/
[read the docs]: https://gridworks-proactor.readthedocs.io/
[tests]: https://github.com/thegridelectric/gridworks-proactor/actions?workflow=Tests
[codecov]: https://app.codecov.io/gh/thegridelectric/gridworks-proactor
[pre-commit]: https://github.com/pre-commit/pre-commit
[black]: https://github.com/psf/black

This packages provides "live actor" and "application monitored communication" infrastructure for the
[GridWorks SpaceHeat SCADA](https://github.com/thegridelectric/gw-scada-spaceheat-python) project. This separation
allows the scada code to be more focussed on on application specific details and provides the potential to re-use the
"live actor" and "application monitored" infrastructure.

## Features

- [](Proactor), a single threaded event loop running on asyncio, for exchanging messages between the main application
  object, "live actor" subobjects and MQTT clients.
- A [communication state] ("active" or not) for each external communications link is available to the proactor and
  sub-objects. "Active" communications is defined as ALL of the following:
  - The underlying communications mechanism (MQTT) is connected.
  - All input channels of underlying mechanism (MQTT topics) are established.
  - A application messages requiring acknowledgement have been ACKed in timely fashion (by default 5 seconds).
  - A message has been received "recently" (by default within 1 minute).
- Reliable delievery of "Events" generated locally. Generated Events are stored locally until they are acknowledged
  and unacknowledged Events are retransmitted when the "Active" communication state is restored.
- [](gwproactor_test), a test package for development and test environments of projects that implement a class derived
  from [](Proactor), allowing the derived class to be tested with the base-class tests.

## Requirements

Testing requires an MQTT broker. This can be installed on a mac with:

```shell
brew install mosquitto
brew services restart mosquitto
```

Alternatively, the MQTT broker used by tests be controlled by .env file as described in [](DefaultTestEnv).

## Installation

You can install _Gridworks Proactor_ via [pip] from [PyPI]:

```console
$ pip install gridworks-proactor
```

## Contributing

Contributions are very welcome. In order to develop, do this:

```console
$ poetry install --all-extras
```

To learn more, see the [Contributor Guide].

## License

Distributed under the terms of the [MIT license][license],
_Gridworks Proactor_ is free and open source software.

## Issues

If you encounter any problems,
please [file an issue] along with a detailed description.

## Credits

This project was generated from [@cjolowicz]'s [Hypermodern Python Cookiecutter] template.

[@cjolowicz]: https://github.com/cjolowicz
[pypi]: https://pypi.org/
[hypermodern python cookiecutter]: https://github.com/cjolowicz/cookiecutter-hypermodern-python
[file an issue]: https://github.com/thegridelectric/gridworks-proactor/issues
[pip]: https://pip.pypa.io/

<!-- github-only -->

[license]: https://github.com/thegridelectric/gridworks-proactor/blob/main/LICENSE
[contributor guide]: https://github.com/thegridelectric/gridworks-proactor/blob/main/CONTRIBUTING.md
[communication state]: https://gridworks-proactor.readthedocs.io/en/latest/comm_state.html
