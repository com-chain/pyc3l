# pyc3l

[![Latest Pypi Version](http://img.shields.io/pypi/v/pyc3l.svg?style=flat)](https://pypi.python.org/pypi/pyc3l/)

This project allow to create python scripts communicating with the
[ComChain](https://com-chain.org/) API.

## Maturity

This code is in alpha stage. It wasn't tested on Windows. API may change.
This is more a draft for an ongoing reflection.

## Features

using ``pyc3l``:

-

## Requirement

This code is for python3 and uses:

- eth_account
- web3
- ecdsa
- tkinter

You can check if tkinter is installed: open python3 and type:

```
>>> import tkinter
>>> tkinter._test()
```

## Installation

You don't need to download the git version of the code as ``pyc3l`` is
available on the PyPI. So you should be able to run:

```bash
pip install pyc3l
```

If you have downloaded the GIT sources, then you could add install
the current version via traditional::

```bash
python setup.py install
```

And if you don't have the GIT sources but would like to get the latest
master or branch from github, you could also::

```
pip install git+https://github.com/0k/pyc3l
```

Or even select a specific revision (branch/tag/commit)::

```
pip install git+https://github.com/0k/pyc3l@master
```

## Usage

TBD

## Contributing

Any suggestions or issues are welcome. Push requests are very welcome,
please check out the guidelines.

### Test

To run the tests::

```
python3 -m unittest test.test_ApiCommunication
```

### Push Request Guidelines

You can send any code. I'll look at it and will integrate it myself in
the code base and leave you as the author. This process can take time and
it'll take less time if you follow the following guidelines:

- check your code with PEP8 or pylint. Try to stick to 80 columns wide.
- separate your commits per smallest concern.
- each commit should pass the tests (to allow easy bisect)
- each functionality/bugfix commit should contain the code, tests,
  and doc.
- prior minor commit with typographic or code cosmetic changes are
  very welcome. These should be tagged in their commit summary with
  ``!minor``.
- the commit message should follow gitchangelog rules (check the git
  log to get examples)
- if the commit fixes an issue or finished the implementation of a
  feature, please mention it in the summary.

If you have some questions about guidelines which is not answered here,
please check the current ``git log``, you might find previous commit that
shows you how to deal with your issue.

## License

Licensed under the [GNU Affero General Public License](GNU Affero
General Public License: http://raw.github.com/0k/pyc3l/master/LICENSE)
