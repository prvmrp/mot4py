# mot4py

## Development

After downloading the project from github, you will need to:

1. Install python 3.11 in some way or form (3.11.2 is preferred).
   
    You can check your python version from the terminal with `python
    --version`. If you find a python 2 version from this command, check
    again with `python3 --version`.

    If you have another version of python installed, a useful way of
    managing different python versions is
    [pyenv](https://github.com/pyenv/pyenv). After having installed
    pyenv, you can run
    ```bash
    pyenv install 3.11.2
    ```
    Then, change to the project directory and run
    ```bash
    pyenv local 3.11.2
    ```
    this will ensure that you will use the correct python version for the
    development of this software.
    To be sure that everything has gone well, check again your python
    version, which should now be 3.11.2.
   
1. Create a virtual environment.
    
    A virtual environment is crucial for the separation between your
    system python packages and those of this package. Click
    [here](https://python.land/virtual-environments/virtualenv) for
    a brief virtualenv tutorial.

    From inside the project directory, run:
    ```bash
    python -m venv .venv
    ```
    Then run:
    - For Linux/Mac: `source .venv/bin/activate`
    - For Windows: `.venv\Scripts/Activate.ps1` (on powershell) or
    `.venv\Scripts\activate.bat` (on cmd)


1. Install setuptools and pip-tools.

    Those are packages needed for packaging and managing dependencies
    during development.

    From inside the project directory, run:
    ```bash
    pip install setuptools pip-tools 
    ```

1. Install all runtime and development dependencies:
    From inside the project library, run:
    ```bash
    make
    ```
    And everything should be installed. If this does not work, and/or
    you do not have make installed, try the following:

    1. Install runtime libraries.

        Runtime libraries and packages are those needed for the execution of
        the program (not the development).

        From inside the project directory, run:
        ```bash
        pip-sync
        ```

    1. Make an editable install of the package.

        In this way, you will install the package from the working
        directory, and you will be able to see the changes in real time.

        From inside the project directory, run:
        ```bash
        pip install -e .
        ```

    1. Install the pre-commit hooks.
        This is done so that the code is automatically formatted on
        commit according to python standards (PEP8).

        From inside the project directory, run:
        ```bash
        pre-commit install
        ```

1. Check that everything is good.
    
    From inside the project directory, run:
    ```bash
    mot4py --help
    ```

    You should see the mot4py help message

1. Hack away and contribute! (Optional)

If you are stuck at any moment, send an email at
`cavicchioli@lens.unifi.it`.
