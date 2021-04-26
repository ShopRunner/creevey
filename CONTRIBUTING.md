# Contributing

## How to Contribute

We welcome contributions in the form of issues or pull requests! 

We want this to be a place where all are welcome to discuss and contribute, so please note that this project is released with a Contributor Code of Conduct. By participating in this project you agree to abide by its terms. Find the code of conduct in the ``CONDUCT.md`` file on GitHub.

If you have a problem using Wildebeest or see a possible improvement, open an issue in the GitHub issue tracker. Please be as specific as you can.

If you see an open issue you'd like to be fixed, take a stab at it and open a PR!

## Steps for Making a Pull Request

1. Fork the project from GitHub. (Internal ShopRunner contributors can just clone the repo and skip to Step 4.)
2. Clone the forked repo to your local disk. 

```bash
git clone https://github.com/<your_github_user_name>/wildebeest.git
```

3. `cd` into the directory.
4. Create a new branch.

```bash
git checkout -b my_awesome_new_feature
```

5. Install the library. (We recommend using a virtual environment.)
    
```bash
pip install -e .
```

6. Install the dev and readthedocs requirements.

```bash
pip install -r requirements-dev.txt -r requirements-read-the-docs.txt
```

7. Make your changes.
8. Open a pull request against our `main` branch. We encourage you to do this step early on, before your changes are completed, so that we know you are working on the issue and can provide input early on.
9. Complete all items in the pull request checklist that you feel comfortable with. Feel free to submit a PR with some loose ends, particularly if you are not sure about how to complete a checklist item.

## Additional Notes

- We prefer single quotes for one-line strings unless using double quotes allows us to avoid escaping internal single quotes.
- We use [numpy style](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_numpy.html) for docstrings.
- We want Wildebeest to be compatible with Python 3.6+.
