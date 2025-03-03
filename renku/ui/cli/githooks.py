#
# Copyright 2018-2023 - Swiss Data Science Center (SDSC)
# A partnership between École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Install and uninstall Git hooks.

Description
~~~~~~~~~~~

The commit hooks are enabled by default to prevent situation when
some output file is manually modified. It also takes care of adding
relevant files to Git LFS and warns of files added to a dataset's
data directory that haven't been added to dataset metadata.


Commands and options
~~~~~~~~~~~~~~~~~~~~

.. rst-class:: cli-reference-commands

.. click:: renku.ui.cli.githooks:githooks
   :prog: renku githooks
   :nested: full


Examples
~~~~~~~~

.. code-block:: console

    $ renku init
    $ renku run echo hello > greeting.txt
    $ edit greeting.txt
    $ git commit greeting.txt
    You are trying to update some output files.

    Modified outputs:
      greeting.txt

    If you are sure, use "git commit --no-verify".

"""

import os
from pathlib import Path

import click

import renku.ui.cli.utils.color as color


@click.group()
def githooks():
    """Manage Git hooks for Renku repository."""


@githooks.command()
@click.option("--force", is_flag=True, help="Override existing hooks.")
def install(force):
    """Install Git hooks."""
    from renku.command.githooks import install_githooks_command
    from renku.ui.cli.utils.callback import ClickCallback

    communicator = ClickCallback()
    result = install_githooks_command().with_communicator(communicator).build().execute(force, path=Path(os.getcwd()))

    warning_messages = result.output
    if warning_messages:
        for message in warning_messages:
            communicator.warn(message)

    click.secho("OK", fg=color.GREEN)


@githooks.command()
def uninstall():
    """Uninstall Git hooks."""
    from renku.command.githooks import uninstall_githooks_command

    uninstall_githooks_command().build().execute()
    click.secho("OK", fg=color.GREEN)
