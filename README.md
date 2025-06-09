# pyc3l

[![Latest Pypi Version](http://img.shields.io/pypi/v/pyc3l.svg?style=flat)](https://pypi.python.org/pypi/pyc3l/)

This project allow to create python scripts communicating with the
[ComChain](https://com-chain.org/) API.

## Maturity

This code is in alpha stage. It wasn't tested on Windows. API may change.
This is more a draft for an ongoing reflection.

## Requirement

This code is for python3 and uses:

- eth_account
- web3
- ecdsa
- requests

It is tested on Python `3.9`, `3.10`, `3.11` and `3.12`.

## Installation

You don't need to download the git version of the code as ``pyc3l`` is
available on the PyPI. So you should be able to run:

```bash
pip install pyc3l
```

If you have downloaded the GIT sources, then you could add install
the current version via traditional::

```bash
pip install .
```

And if you don't have the GIT sources but would like to get the latest
master or branch from github, you could also::

```
pip install git+https://github.com/com-chain/pyc3l
```

Or even select a specific revision (branch/tag/commit)::

```
pip install git+https://github.com/com-chain/pyc3l@master
```

## Usage

```python
from pyc3l import Pyc3l

## Instantiate our interface to Comchain's node
#pyc3l = Pyc3l()
pyc3l = Pyc3l(block_number="pending")  ## default

## load your ciphered wallet
wallet = pyc3l.Wallet.from_json(json_string_wallet)

## use the ``wallet`` object to read the blockchain

wallet.isValidAdmin
wallet.status

wallet.globalBalance
wallet.nantBalance
wallet.cmBalance
wallet.cmLimitMin
wallet.cmLimitMax

wallet.Allowances        ## dict of {address: amount}
wallet.Requests          ## dict of {address: amount}
wallet.MyRequests        ## dict of {address: amount}
wallet.Delegations       ## dict of {address: amount}
wallet.MyDelegations     ## dict of {address: amount}
wallet.AcceptedRequests  ## dict of {address: amount}
wallet.RejectedRequests  ## dict of {address: amount}


## use the ``wallet`` object to emit transaction

## unlock your wallet with your password
wallet.unlock(mypassword)

wallet.enable(address)
wallet.disable(address)

wallet.pledge(address, amount, amount,  message_from="", message_to="")
wallet.delegate(address, amount)

wallet.transferNant(address, amount, message_from="", message_to="")
wallet.transferOnBehalfOf(address_from, address_to, amount, message_from="", message_to="")


## Get the currency object

currency = Currency("Lemanopolis")
## or from wallet:
currency = wallet.currency

currency.getAmountPledged()  ## total pledged amount


## get account in a currency

account = currency.Account("0x...")

account.nonce_hex
account.nonce_dec
account.eth_balance
account.eth_balance_gwei
account.eth_balance_eth

account.active
account.owner
account.role

account.allowances         ## dict of {address: amount}
account.requests           ## dict of {address: amount}
account.my_requests        ## dict of {address: amount}
account.delegations        ## dict of {address: amount}
account.my_delegations     ## dict of {address: amount}
account.accepted_requests  ## dict of {address: amount}
account.rejected_requests  ## dict of {address: amount}


```

Please note that ``pyc3l-cli`` package has a lot of short and simple
scripts to showcase the usage of the library.

## Contributing

Any suggestions or issues are welcome. Push requests are very welcome,
please check out the guidelines.

### Test

To run the tests, you'll need to install `hatch` and::

```
hatch run test
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
General Public License: http://raw.github.com/com-chain/pyc3l/master/LICENSE)
